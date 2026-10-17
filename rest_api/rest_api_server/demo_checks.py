"""Guided presentation UI. Exercises real HTTP endpoints using the current account."""
from datetime import datetime, timezone
import json
import httpx


def run_demo_check(base_url, token, label, method, path, expected_status, payload=None, authentication='bearer'):
    headers = {'Authorization': f'Bearer {token}'} if authentication == 'bearer' else {'Authorization': 'Bearer deliberately-invalid-token'} if authentication == 'invalid' else {}
    try:
        response = httpx.request(method, base_url + path, json=payload, headers=headers, timeout=15, follow_redirects=False)
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = {'detail': 'Non-JSON response'}
        return {'check': label, 'method': method, 'path': path,
                'expected': expected_status, 'actual': response.status_code,
                'passed': response.status_code == expected_status, 'response': body,
                'request_id': response.headers.get('X-Request-ID'),
                'authorization': 'Bearer <redacted>' if headers else 'No Authorization header',
                'time': datetime.now(timezone.utc).isoformat()}
    except httpx.HTTPError as error:
        return {'check': label, 'method': method, 'path': path, 'expected': expected_status,
                'actual': None, 'passed': False, 'response': {'detail': str(error)},
                'time': datetime.now(timezone.utc).isoformat()}


def render_demo(base_url, profile, permissions, data):
    import streamlit as st

    token = st.session_state['access_token']
    role = profile['role']
    actions = permissions['resources']
    history_key = f"demo_results_{profile['id']}"
    history = st.session_state.setdefault(history_key, [])

    def check(label, method, path, expected, payload=None, authentication='bearer'):
        result = run_demo_check(base_url, token, label, method, path, expected, payload, authentication)
        result['role'] = role
        history.append(result)
        if result['passed']:
            st.success(f"{label}: HTTP {result['actual']} — expected {expected}")
        else:
            st.error(f"{label}: expected {expected}, received {result['actual'] or 'connection failure'}")
        st.json(result)
        return result

    st.subheader('Authentication & authorization walkthrough')
    st.write('Run each step as tenant.admin, org.admin and viewer to compare the same actions. Use platform.admin to show platform-wide access.')
    st.caption('Authentication identifies the caller. Authorization checks the action and the resource scope. These checks call the API directly, even when normal workspace controls hide an action.')
    st.dataframe([{'Account': name, 'Role': role_name, 'Scope': scope} for name, role_name, scope in [
        ('platform.admin', 'platform_admin', 'All tenants'), ('tenant.admin', 'tenant_admin', 'Own tenant'),
        ('org.admin', 'organization_admin', 'Own organization'), ('viewer', 'viewer', 'Assigned scope')]], hide_index=True, width='stretch')
    st.caption('Seeded accounts require SEED_DEMO=true and your configured DEMO_PASSWORD. Custom accounts work too. Log out in the sidebar to change accounts.')

    with st.container(border=True):
        st.markdown('### 1. Prove authentication')
        st.write('The same profile endpoint should reject missing/invalid bearer tokens and accept your login token.')
        if st.button('Run authentication checks'):
            check('Missing bearer token', 'GET', '/api/v1/users/me', 401, authentication='none')
            check('Invalid bearer token', 'GET', '/api/v1/users/me', 401, authentication='invalid')
            check('Valid bearer token', 'GET', '/api/v1/users/me', 200)
        st.json({'username': profile['username'], 'role': role, 'tenant_id': profile['tenant_id'],
                 'organization_id': profile['organization_id'], 'scope': permissions['scope']})

    with st.container(border=True):
        st.markdown('### 2. Show role grants')
        st.dataframe([{'Resource': resource, 'Allowed actions': ', '.join(grants)} for resource, grants in actions.items()], hide_index=True, width='stretch')
        st.write('403 means this role does not grant the action. A grant still requires the target to be inside your tenant/organization.')
        for restriction in permissions['restrictions']:
            st.caption(restriction)

    with st.container(border=True):
        st.markdown('### 3. Exercise tenant and organization actions')
        resource = st.selectbox('Demo resource level', ['tenants', 'organizations'], key='demo_resource')
        records = {row['id']: row for row in data[resource]}
        if not records:
            st.info('No accessible records at this level. Create one using an administrator account first.')
        else:
            record_id = st.selectbox('Demo target', list(records), format_func=lambda value: f"{records[value]['name']} · {value}", key=f'demo_target_{resource}')
            record = records[record_id]
            st.caption(f"Target tenant: {record['id'] if resource == 'tenants' else record['tenant_id']}" + (f" · Organization: {record['id']}" if resource == 'organizations' else ''))
            expected_update = 200 if 'update' in actions[resource] else 403
            st.write(f"Read → expected 200. Update → expected {expected_update} for {role}.")
            if st.button('Check read access'):
                check(f'Read {resource}', 'GET', f'/api/v1/{resource}/{record_id}', 200)
            with st.form(f'demo_update_{resource}_{record_id}'):
                name = st.text_input('Demo name', value=record['name'], help='Keeping the current name exercises the write path without changing the visible name. A different name is saved when permitted.')
                st.caption('This performs a real PATCH. Keeping the current name is sufficient to demonstrate authorization.')
                if st.form_submit_button('Check update access'):
                    if not name.strip() or len(name.strip()) > 120:
                        st.error('Enter a name from 1 to 120 characters.')
                    else:
                        check(f'Update {resource}', 'PATCH', f'/api/v1/{resource}/{record_id}', expected_update, {'name': name})
            with st.expander('Demonstrate create and delete'):
                st.caption('Creates a separate demo record. Use the cleanup button to remove only records created here.')
                with st.form(f'demo_create_{resource}_{record_id}'):
                    new_name = st.text_input('New demo record name', value='Authorization demo')
                    if st.form_submit_button('Check create access'):
                        if not new_name.strip() or len(new_name.strip()) > 120:
                            st.error('Enter a name from 1 to 120 characters.')
                        else:
                            payload = {'name': new_name}
                            if resource == 'organizations':
                                payload['tenant_id'] = record['tenant_id']
                            result = check(f'Create {resource}', 'POST', f'/api/v1/{resource}', 201 if 'create' in actions[resource] else 403, payload)
                            if result['actual'] == 201:
                                st.session_state.setdefault(f'demo_created_{profile["id"]}', []).append({'resource': resource, 'record': result['response']})
                created = st.session_state.get(f'demo_created_{profile["id"]}', [])
                for item in list(created):
                    row = item['record']
                    st.write(f"Created {item['resource']}: {row['name']} · {row['id']}")
                    if st.button(f"Delete demo record {row['id'][:8]}", key=f"cleanup_{row['id']}"):
                        result = check(f"Delete demo {item['resource']}", 'DELETE', f"/api/v1/{item['resource']}/{row['id']}", 204 if 'delete' in actions[item['resource']] else 403)
                        if result['actual'] == 204:
                            created.remove(item)

    with st.container(border=True):
        st.markdown('### 4. Prove tenant/organization isolation')
        st.write('As platform.admin, copy an existing tenant ID from a different tenant, or an organization ID from outside the demo account’s scope. Log in as the scoped account and paste it here.')
        st.caption('A random/nonexistent ID also returns 404; use a known existing record to demonstrate isolation.')
        with st.form('demo_scope_check'):
            scope_resource = st.selectbox('Out-of-scope resource', ['tenants', 'organizations'])
            outside_id = st.text_input('Known existing target ID')
            confirmed = st.checkbox('This record exists and is outside this account’s assigned scope (unless platform admin)')
            if st.form_submit_button('Check scope isolation'):
                if not outside_id.strip() or not confirmed:
                    st.warning('Provide a known existing target and confirm its scope.')
                else:
                    check('Resource scope isolation', 'GET', f'/api/v1/{scope_resource}/{outside_id.strip()}', 200 if role == 'platform_admin' else 404)

    st.subheader('Demo evidence')
    st.caption('Only checks run on this page appear here. Expected 401/403/404 responses count as successful checks. Tokens and passwords are excluded. History is cleared on logout.')
    if history:
        st.dataframe([{key: result.get(key) for key in ('time', 'role', 'check', 'method', 'path', 'expected', 'actual', 'passed')} for result in history], hide_index=True, width='stretch')
        st.download_button('Download demo evidence', json.dumps(history, indent=2), file_name='authorization_demo.json', mime='application/json')
        if st.button('Clear demo evidence'):
            st.session_state[history_key] = []
            st.rerun()
    else:
        st.info('Run the checks above to collect evidence for your presentation.')
