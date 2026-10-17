"""Present the asynchronous REST -> database outbox -> RabbitMQ -> worker flow."""
def render_worker_dashboard(profile, tenants, actions, request):
    import streamlit as st
    st.subheader('Exchange-rate worker demo')
    st.code('POST job → MySQL queued job/outbox → RabbitMQ → worker → ExchangeRate-API → MySQL result\nGET job ← status + attempts + rates', language=None)
    st.caption('The API returns 202 immediately. A separate container performs the external request. No ExchangeRate-API call is made in the request handler.')
    by_id = {tenant['id']:tenant for tenant in tenants}
    if not by_id:
        st.info('Choose an accessible tenant first.')
        return
    tenant_id = st.selectbox('Worker tenant',list(by_id),format_func=lambda value:by_id[value]['name'])
    path = f'/api/v1/tenants/{tenant_id}/exchange-rate-jobs'
    if 'create' in actions.get('exchange-rate-jobs',[]):
        with st.form('submit_exchange_rate_job'):
            base = st.text_input('Base currency',value='USD',max_chars=3)
            st.caption('Defaults to USD. Requests time out after 10 seconds. Organization-scoped callers create jobs in their assigned organization.')
            if st.form_submit_button('Queue exchange-rate job'):
                result = request('POST',path,payload={'base_currency':base.strip().upper(), 'organization_id':profile['organization_id']})
                if result is not None:
                    st.success(f"Accepted job {result['id']}. The worker processes it independently.")
    else:
        st.info('Your role can inspect accessible jobs but cannot submit them.')
    st.button('Refresh worker jobs')
    jobs = request('GET',path+'?limit=50')
    if jobs is None:
        return
    st.caption('Latest page of up to 50 accessible jobs. Refresh to observe queued → running → succeeded/failed. Fast jobs may complete between refreshes.')
    if not jobs:
        st.info('No jobs yet. Submit one with a tenant or organization administrator account.')
    else:
        st.dataframe([{field:job[field] for field in ('id','base_currency','status','attempts','created_at','started_at','finished_at','error')} for job in jobs],hide_index=True,width='stretch')
        by_job = {job['id']:job for job in jobs}
        job_id = st.selectbox('Inspect worker job',list(by_job),format_func=lambda value:f"{by_job[value]['base_currency']} · {by_job[value]['status']} · {value[:8]}")
        job = request('GET',path+'/'+job_id)
        if job:
            st.json({key:value for key,value in job.items() if key!='result'})
            if job['status']=='succeeded' and job['result']:
                st.success('Worker completed the external request and saved the result.')
                st.caption(f"Base: {job['result']['base_currency']} · Provider updated: {job['result'].get('provider_updated_at')}")
                st.dataframe([{'Currency':code,'Rate':rate} for code,rate in job['result']['rates'].items()],hide_index=True,width='stretch')
            elif job['status']=='failed':
                st.error(job['error'])
            else:
                st.info('Pending worker completion. Refresh to update status.')
    with st.expander('Presentation steps and troubleshooting'):
        st.write('1. Queue a USD job and show HTTP 202 in the last API request panel.\n2. Inspect the job status and attempts.\n3. Open RabbitMQ management at http://localhost:15672 and inspect exchange-rate-jobs.\n4. Show worker logs with the command below.\n5. Refresh this page and inspect the stored currency table.')
        st.code('docker compose --project-directory rest_api logs -f worker',language='shell')
        st.caption('Pause the worker to demonstrate a queued job, then resume it. An empty queue may mean the worker already consumed the job. Missing/invalid API keys become failed jobs; timeouts and temporary provider errors retry up to three attempts. Keys are configured on the worker, never entered or returned here.')
