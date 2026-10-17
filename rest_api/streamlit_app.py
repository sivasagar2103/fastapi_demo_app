"""Interactive HTTP client; all domain work is performed by the FastAPI backend."""
import os
import httpx
import streamlit as st

st.set_page_config(page_title="Organization Workspace", page_icon="🏢", layout="wide")
st.title("Organization Workspace")
st.caption("Explore your tenants, organizations, people and teams in one place.")

base_url = st.sidebar.text_input("API URL", os.getenv("API_BASE_URL", "http://localhost:8000")).rstrip("/")
if st.session_state.get("api_url") != base_url:
    st.session_state.clear()
    st.session_state.api_url = base_url


def request(method, path, *, payload=None, form=None, public=False):
    token = st.session_state.get('access_token')
    if not public and not token:
        st.warning('Sign in first to send an Authorization bearer header.')
        return None
    headers = {} if public else {'Authorization': f'Bearer {token}'}
    try:
        response = httpx.request(method, base_url + path, json=payload, data=form,
                                 headers=headers, timeout=15, follow_redirects=False)
    except httpx.HTTPError as error:
        st.error(f'Cannot reach API: {error}')
        return None
    st.session_state.last_request = {'method': method, 'path': path, 'status': response.status_code, 'request_id': response.headers.get('X-Request-ID'), 'authorization': 'Bearer ••••••••' if not public else 'Public endpoint'}
    if response.status_code == 204:
        st.success('Completed')
        return {}
    try:
        result = response.json()
    except ValueError:
        st.error('API returned a non-JSON response.')
        return None
    if response.is_error:
        st.error(result.get('detail', result))
        if response.status_code == 401 and not public:
            st.session_state.pop('access_token', None)
        return None
    return result


def remember_token(result):
    if result:
        st.session_state.pop('tenant_id', None)
        st.session_state.pop('organization_id', None)
        st.session_state.access_token = result['access_token']
        st.session_state.expires_in = result['expires_in']
        st.rerun()


if not st.session_state.get('access_token'):
    login, register = st.tabs(['Login', 'Register'])
    with login:
        with st.form('login', clear_on_submit=True):
            username = st.text_input('Username', key='login_username')
            password = st.text_input('Password', type='password', key='login_password')
            if st.form_submit_button('Login and generate token'):
                remember_token(request('POST', '/api/v1/users/login', payload={'username': username, 'password': password}, public=True))
    with register:
        st.caption('Registration creates a separate tenant. Choose a demo role, or leave the default tenant administrator role. Organization administrators receive a default organization.')
        with st.form('register', clear_on_submit=True):
            new_username = st.text_input('Username', key='register_username')
            new_password = st.text_input('Password (at least 12 characters)', type='password', key='register_password')
            tenant_name = st.text_input('Tenant name (optional; new tenant only)')
            registration_role = st.selectbox('Role (optional)', [None, 'tenant_admin', 'organization_admin', 'viewer'], format_func=lambda value: 'Default — Tenant administrator' if value is None else value.replace('_', ' ').title(), key='registration_role')
            st.caption('Viewer registrations have read-only access. Platform administrators are provisioned separately.')
            if st.form_submit_button('Register and sign in'):
                remember_token(request('POST', '/api/v1/users/register', payload={'username': new_username, 'password': new_password, 'tenant_name': tenant_name or None, **({'role': registration_role} if registration_role else {})}, public=True))
    
    st.info("Login or register to open your workspace.")
    st.stop()


def navigate(page):
    st.session_state.page = page


def clear_organization():
    st.session_state.pop('organization_id', None)


def load_records(resource):
    """Read all server pages so hierarchy filtering and counts are complete."""
    records = []
    while True:
        page = request('GET', f'/api/v1/{resource}?offset={len(records)}&limit=100')
        if page is None:
            st.error(f'Could not load {resource}. Check the API connection or sign in again.')
            if not st.session_state.get('access_token'):
                st.rerun()
            st.stop()
        records.extend(page)
        if len(page) < 100:
            return records


def save_resource(resource, payload, record_id=None):
    path = f'/api/v1/{resource}' + (f'/{record_id}' if record_id else '')
    result = request('PATCH' if record_id else 'POST', path, payload=payload)
    if result is not None:
        st.session_state.notice = 'Changes saved.'
        st.rerun()


def display_table(title, records, columns):
    st.subheader(title)
    search = st.text_input('Search this table', key=f'search_{title}', placeholder='Search names, emails, roles…')
    rows = []
    for record in records:
        row = {label: value(record) if callable(value) else record.get(value, '') for label, value in columns.items()}
        if not search or search.casefold() in ' '.join(str(value) for value in row.values()).casefold():
            rows.append(row)
    if rows:
        st.dataframe(rows, width='stretch', hide_index=True)
        st.download_button('Download CSV', data=to_csv(rows), file_name=title.lower().replace(' ', '_')+'.csv', mime='text/csv', key=f'csv_{title}')
    else:
        st.info('No matching records. Adjust your scope/search or create a record below.')
    st.caption(f'{len(rows)} shown · {len(records)} records in this scope')


def to_csv(rows):
    import csv
    import io
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    # Keep exported names safe to open as literal values in spreadsheet tools.
    writer.writerows({key: "'"+value if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value for key, value in row.items()} for row in rows)
    return stream.getvalue()


profile = request('GET', '/api/v1/users/me')
if profile is None:
    if not st.session_state.get('access_token'):
        st.rerun()
    st.stop()
role = profile['role']
st.sidebar.markdown(f"**{profile['username']}**")
st.sidebar.caption(role.replace('_', ' ').title())
if st.sidebar.button('Log out'):
    st.session_state.clear()
    st.rerun()

permissions = request('GET', '/api/v1/users/me/permissions')
if permissions is None:
    st.stop()
actions = permissions['resources']

if st.session_state.get('notice'):
    st.success(st.session_state.pop('notice'))

# HTTP remains the only data access boundary; authorization is enforced by the API.
data = {resource: load_records(resource) for resource in ('tenants', 'organizations', 'users', 'employees', 'employee-groups')}
tenants_by_id = {record['id']: record['name'] for record in data['tenants']}
orgs_by_id = {record['id']: record['name'] for record in data['organizations']}

st.sidebar.divider()
st.sidebar.subheader('Browse hierarchy')
tenant_options = [None] + list(tenants_by_id)
if st.session_state.get('tenant_id') not in tenant_options:
    st.session_state.tenant_id = None
selected_tenant = st.sidebar.selectbox('Tenant', tenant_options, format_func=lambda value: tenants_by_id.get(value, 'All tenants'), key='tenant_id', on_change=clear_organization)
organizations = [record for record in data['organizations'] if not selected_tenant or record['tenant_id'] == selected_tenant]
organization_options = [None] + [record['id'] for record in organizations]
if st.session_state.get('organization_id') not in organization_options:
    st.session_state.organization_id = None
selected_org = st.sidebar.selectbox('Organization', organization_options, format_func=lambda value: orgs_by_id.get(value, 'All organizations'), key='organization_id')
# An organization selected from "All tenants" still defines its parent tenant.
context_tenant = selected_tenant or next((record['tenant_id'] for record in organizations if record['id'] == selected_org), None)
page = st.sidebar.radio('Tables', ['Overview', 'Tenants', 'Organizations', 'Users', 'Employees', 'Employee groups', 'Permissions', 'Auth demo', 'Tenant assistant', 'Worker jobs'], key='page')
if st.sidebar.button('Refresh data'):
    st.rerun()
with st.sidebar.expander('Account details'):
    st.json(profile)
with st.sidebar.expander('Last API request'):
    st.json(st.session_state.get('last_request', {}))

scoped = {
    'tenants': [record for record in data['tenants'] if not context_tenant or record['id'] == context_tenant],
    'organizations': [record for record in organizations if not selected_org or record['id'] == selected_org],
}
for resource in ('users', 'employees', 'employee-groups'):
    scoped[resource] = [record for record in data[resource]
                        if (not context_tenant or record.get('tenant_id') == context_tenant)
                        and (not selected_org or record.get('organization_id') == selected_org
                             or (resource == 'users' and record.get('organization_id') is None))]

path = ['Workspace']
if context_tenant:
    path.append(tenants_by_id.get(context_tenant, 'Tenant'))
if selected_org:
    path.append(orgs_by_id[selected_org])
if page != 'Overview':
    path.append(page)
st.caption('  ›  '.join(path))
left, right = st.columns([4, 1])
with left:
    st.header(page)
with right:
    st.button('Workspace overview', on_click=navigate, args=('Overview',))

if page == 'Worker jobs':
    from rest_api_server.worker_dashboard import render_worker_dashboard
    render_worker_dashboard(profile, scoped['tenants'], actions, request)
    st.stop()

if page == 'Tenant assistant':
    from rest_api_server.summary_dashboard import render_summary
    render_summary(base_url, profile, scoped['tenants'])
    st.stop()

if page == 'Auth demo':
    from rest_api_server.demo_checks import render_demo
    render_demo(base_url, profile, permissions, data)
    st.stop()

if page == 'Permissions':
    st.subheader('What can I do?')
    st.caption(f"Role: {role} · Scope: {permissions['scope']} · Tenant: {profile['tenant_id'] or 'All'} · Organization: {profile['organization_id'] or 'All within scope'}")
    st.dataframe([{'Resource': resource, **{action.replace('_', ' ').title(): action in granted for action in ('read', 'create', 'update', 'delete', 'manage_members')}} for resource, granted in actions.items()], hide_index=True, width='stretch')
    st.subheader('Rules applied to these grants')
    for restriction in permissions['restrictions']:
        st.write('• '+restriction)
    st.info('Allowed actions still require a matching tenant/organization. Requests outside your scope return 404; prohibited actions return 403.')
    st.stop()

if page == 'Overview':
    st.success(f"Signed in as {profile['username']} · Role: {role.replace('_', ' ').title()} · Access: {permissions['scope'].title()} scope")
    with st.expander('My allowed actions'):
        st.dataframe([{'Resource': resource, 'Actions': ', '.join(granted)} for resource, granted in actions.items()], hide_index=True, width='stretch')
    columns = st.columns(5)
    for column, label, resource in zip(columns, ['Tenants', 'Organizations', 'Users', 'Employees', 'Groups'], scoped):
        column.metric(label, len(scoped[resource]))
    st.subheader('Tenant → Organization → People and teams')
    if not scoped['tenants']:
        st.info('No tenants are available for this account.')
    for tenant in scoped['tenants']:
        with st.expander(tenant['name'], expanded=True):
            tenant_orgs = [org for org in scoped['organizations'] if org['tenant_id'] == tenant['id']]
            st.caption(f"Tenant ID: {tenant['id']}")
            if not tenant_orgs:
                st.info('No organizations yet. Open Organizations to create one.')
            for org in tenant_orgs:
                employees = [row for row in scoped['employees'] if row['organization_id'] == org['id']]
                groups = [row for row in scoped['employee-groups'] if row['organization_id'] == org['id']]
                with st.container(border=True):
                    st.markdown(f"**{org['name']}**")
                    st.caption(f"{len(employees)} employees · {len(groups)} groups")
                    a, b = st.columns(2)
                    a.write('Employees: '+(', '.join(row['name'] for row in employees) or 'None yet'))
                    b.write('Groups: '+(', '.join(row['name'] for row in groups) or 'None yet'))
    st.info('Choose a tenant and organization in the sidebar, then open an individual table to manage its records.')
    st.stop()

resource = {'Tenants': 'tenants', 'Organizations': 'organizations', 'Users': 'users', 'Employees': 'employees', 'Employee groups': 'employee-groups'}[page]
records = scoped[resource]
columns = {'Name': 'name'} if resource != 'users' else {'Username': 'username', 'Role': 'role', 'Active': 'active'}
if resource == 'employees':
    columns.update({'Email': 'email', 'Job title': 'job_title'})
if resource != 'tenants':
    columns['Tenant'] = lambda row: tenants_by_id.get(row.get('tenant_id'), 'Platform')
if resource in ('users', 'employees', 'employee-groups'):
    columns['Organization'] = lambda row: orgs_by_id.get(row.get('organization_id'), 'Tenant-wide' if row.get('tenant_id') else 'Platform')
columns.update({'ID': 'id', 'Created at': 'created_at'})
display_table(page, records, columns)
if page == 'Users' and selected_org:
    st.caption('Tenant-wide users are included because their access also applies to this organization.')

can_create = 'create' in actions[resource]
can_update = 'update' in actions[resource]
can_delete = 'delete' in actions[resource]
if not any((can_create, can_update, can_delete)):
    st.caption('Your role has read access to this table.')

if can_create:
    with st.expander(f'Create {page.lower()}', expanded=not records):
        valid_context = resource == 'tenants' or bool(context_tenant if resource in ('organizations', 'users') else selected_org)
        if not valid_context:
            st.info('Select a tenant in the sidebar first.' if resource in ('organizations', 'users') else 'Select an organization in the sidebar first.')
        else:
            with st.form(f'create_{resource}_{selected_org or context_tenant}', clear_on_submit=True):
                if resource == 'users':
                    username = st.text_input('Username')
                    password = st.text_input('Initial password', type='password')
                    roles = ['viewer', 'organization_admin'] if selected_org else ['viewer']
                    if role == 'platform_admin' and not selected_org:
                        roles.append('tenant_admin')
                    new_role = st.selectbox('Role', roles)
                    payload = {'username': username, 'password': password, 'role': new_role, 'tenant_id': context_tenant, 'organization_id': selected_org}
                else:
                    name = st.text_input('Name')
                    payload = {'name': name}
                    if resource == 'organizations':
                        payload['tenant_id'] = context_tenant
                    elif resource in ('employees', 'employee-groups'):
                        payload['organization_id'] = selected_org
                    if resource == 'employees':
                        payload.update(email=st.text_input('Email'), job_title=st.text_input('Job title'))
                if st.form_submit_button('Create record'):
                    save_resource(resource, payload)

if records and (can_update or can_delete):
    with st.expander('Edit or delete a record'):
        by_id = {row['id']: row for row in records}
        record_id = st.selectbox('Record', list(by_id), format_func=lambda value: f"{by_id[value].get('name', by_id[value].get('username'))} · {value[:8]}", key=f'edit_{resource}_{selected_org or context_tenant}')
        record = by_id[record_id]
        if can_update:
            with st.form(f'edit_form_{resource}_{record_id}'):
                if resource == 'users':
                    payload = {'active': st.checkbox('Active', value=record['active'])}
                else:
                    payload = {'name': st.text_input('Name', value=record['name'])}
                    if resource == 'employees':
                        payload.update(email=st.text_input('Email', value=record['email']), job_title=st.text_input('Job title', value=record['job_title']))
                if st.form_submit_button('Save changes'):
                    save_resource(resource, payload, record_id)
        if can_delete:
            confirmation = st.checkbox('Confirm deletion', key=f'delete_confirm_{record_id}')
            if st.button('Delete record', disabled=not confirmation, key=f'delete_{record_id}'):
                result = request('DELETE', f'/api/v1/{resource}/{record_id}')
                if result is not None:
                    st.session_state.notice = 'Record deleted.'
                    st.rerun()


if resource == 'employee-groups' and records:
    st.divider()
    st.subheader('Group membership')
    groups_by_id = {record['id']: record for record in records}
    group_id = st.selectbox('Group', list(groups_by_id), format_func=lambda value: groups_by_id[value]['name'], key=f'group_{selected_org or context_tenant}')
    group = groups_by_id[group_id]
    members = request('GET', f'/api/v1/employee-groups/{group_id}/members')
    if members is not None:
        display_table('Members', members, {'Name': 'name', 'Email': 'email', 'Job title': 'job_title', 'ID': 'id'})
        if 'manage_members' in actions[resource]:
            member_ids = {member['id'] for member in members}
            candidates = {employee['id']: employee for employee in scoped['employees'] if employee['organization_id'] == group['organization_id'] and employee['id'] not in member_ids}
            a, b = st.columns(2)
            with a:
                if candidates:
                    employee_id = st.selectbox('Employee to add', list(candidates), format_func=lambda value: candidates[value]['name'], key=f'add_member_{group_id}')
                    if st.button('Add member'):
                        if request('PUT', f'/api/v1/employee-groups/{group_id}/members/{employee_id}') is not None:
                            st.rerun()
                else:
                    st.caption('No more employees to add from this organization.')
            with b:
                if members:
                    by_id = {member['id']: member for member in members}
                    employee_id = st.selectbox('Member to remove', list(by_id), format_func=lambda value: by_id[value]['name'], key=f'remove_member_{group_id}')
                    if st.button('Remove member'):
                        if request('DELETE', f'/api/v1/employee-groups/{group_id}/members/{employee_id}') is not None:
                            st.rerun()
