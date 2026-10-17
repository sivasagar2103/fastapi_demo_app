"""Streamlit consumer for the bearer-protected SSE summary endpoint."""
import json
import httpx


def parse_events(lines):
    event, parts = 'message', []
    for line in lines:
        if not line:
            if parts:
                yield event, json.loads('\n'.join(parts))
            event, parts = 'message', []
        elif line.startswith('event:'):
            event = line[6:].strip()
        elif line.startswith('data:'):
            parts.append(line[5:].lstrip())
    if parts:
        yield event, json.loads('\n'.join(parts))


def render_summary(base_url, profile, tenants):
    import streamlit as st
    st.subheader('Tenant assistant')
    st.caption('Ask about tenant structure, team counts and role permissions. Answers use a fresh authorized snapshot. Management buttons open the normal forms; changes are confirmed there.')
    by_id = {tenant['id']: tenant for tenant in tenants}
    if not by_id:
        st.info('Select an accessible tenant first.')
        return
    tenant_id = st.selectbox('Conversation tenant', list(by_id), format_func=lambda value: by_id[value]['name'])
    st.info(f"Tenant: {by_id[tenant_id]['name']} · Role: {profile['role']} · Organization: {profile['organization_id'] or 'All accessible organizations'}")
    key = f"tenant_chat_{profile['id']}_{tenant_id}_{profile['organization_id']}_{profile['role']}"
    messages = st.session_state.setdefault(key, [])

    def open_workspace(page):
        st.session_state.page = page
        st.session_state.tenant_id = tenant_id
        st.session_state.organization_id = profile['organization_id']

    st.markdown('**Workspace controls**')
    columns = st.columns(5)
    for column, page in zip(columns, ['Organizations', 'Employees', 'Employee groups', 'Users', 'Permissions']):
        column.button(page, on_click=open_workspace, args=(page,), key=f'chat_open_{page}')
    st.caption('These open the corresponding tables. Controls and API permissions enforce your role. The assistant does not modify data.')
    with st.expander('What can I ask?'):
        st.write('• Summarize this tenant and its organizations.\n• How many employees and groups are visible to me?\n• What actions can my role perform?\n• How do I add an employee to a group?\n• Why can I not create an organization?')
    if st.button('Clear conversation'):
        st.session_state[key] = []
        st.rerun()
    for message in messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
    summary_clicked = st.button('Summarize current tenant')
    question = st.chat_input('Ask about this tenant, its data or management flow', max_chars=2000)
    if summary_clicked:
        question = 'Summarize this tenant, explain my visible scope, and suggest relevant workspace controls.'
    if not question:
        return
    history = [{'role':item['role'], 'content':item['content'][:4000]} for item in messages[-10:]]
    messages.append({'role':'user','content':question})
    with st.chat_message('user'):
        st.markdown(question)
    completed = False
    def chunks():
        nonlocal completed
        with httpx.stream('POST', f'{base_url}/api/v1/tenants/{tenant_id}/chat/stream',
                headers={'Authorization':f"Bearer {st.session_state['access_token']}"},
                json={'question':question, 'history':history},
                timeout=httpx.Timeout(120, connect=10), follow_redirects=False) as response:
            if response.status_code != 200:
                response.read()
                try:
                    message = response.json().get('detail', 'Assistant unavailable')
                except ValueError:
                    message = 'Assistant unavailable'
                raise ValueError(f'HTTP {response.status_code}: {message}')
            for event, data in parse_events(response.iter_lines()):
                if event == 'snapshot':
                    with st.expander('Source data and effective permissions'):
                        st.json(data)
                elif event == 'delta':
                    yield data['text']
                elif event == 'error':
                    raise ValueError(data['detail'])
                elif event == 'done':
                    completed = True
    with st.chat_message('assistant'):
        try:
            text = st.write_stream(chunks())
            if completed and isinstance(text, str) and text:
                messages.append({'role':'assistant', 'content':text})
                st.success('Answer complete')
                st.download_button('Download answer', text, file_name='tenant_answer.md', mime='text/markdown')
            else:
                st.error('Stream ended before completion. Any displayed text is partial.')
        except (httpx.HTTPError, ValueError, KeyError) as error:
            st.error(f'{error}. Any displayed text is partial and will not be reused as assistant history.')
        # Bound per-tenant memory; only the latest ten messages go to Azure.
        st.session_state[key] = messages[-40:]
