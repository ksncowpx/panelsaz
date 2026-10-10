import aiohttp
import asyncio
import random
import string

RAILWAY_GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"
GITHUB_REPO = "hdzirxluci-hub/pablo-panel"

async def execute_graphql(token: str, query: str, variables: dict = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"query": query, "variables": variables or {}}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(RAILWAY_GRAPHQL_URL, json=payload, headers=headers) as resp:
            if resp.status != 200:
                return None, f"خطای سرور ریلوی: {resp.status}"
            data = await resp.json()
            if "errors" in data:
                return None, data["errors"][0]["message"]
            return data.get("data"), None

# بررسی اعتبار توکن کاربر
async def validate_railway_token(token: str):
    query = """
    query {
        me {
            id
            email
            name
        }
    }
    """
    data, error = await execute_graphql(token, query)
    if error or not data or not data.get("me"):
        return False, "توکن نامعتبر است یا منقضی شده است."
    return True, data["me"]["email"]

# ساخت پروژه و دیپلوی پابلو پنل
async def deploy_pablo(token: str):
    rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    project_name = f"pablo-panel-{rand_str}"

    # ۱. ساخت پروژه جدید
    create_project_query = """
    mutation projectCreate($input: ProjectCreateInput!) {
        projectCreate(input: $input) {
            id
            environments {
                edges {
                    node {
                        id
                    }
                }
            }
        }
    }
    """
    data, err = await execute_graphql(token, create_project_query, {"input": {"name": project_name}})
    if err: return None, err
    
    project_id = data["projectCreate"]["id"]
    environment_id = data["projectCreate"]["environments"]["edges"][0]["node"]["id"]

    # ۲. ایجاد سرویس و اتصال به گیت‌هاب پابلو پنل
    create_service_query = """
    mutation serviceCreate($input: ServiceCreateInput!) {
        serviceCreate(input: $input) {
            id
        }
    }
    """
    data, err = await execute_graphql(token, create_service_query, {
        "input": {
            "projectId": project_id,
            "source": {"repo": GITHUB_REPO}
        }
    })
    if err: return None, err
    service_id = data["serviceCreate"]["id"]

    # چند ثانیه وقفه برای پردازش
    await asyncio.sleep(3)

    # ۳. ساخت دامنه اختصاصی (Generate Domain)
    create_domain_query = """
    mutation serviceDomainCreate($input: ServiceDomainCreateInput!) {
        serviceDomainCreate(input: $input) {
            domain
        }
    }
    """
    data, err = await execute_graphql(token, create_domain_query, {
        "input": {
            "environmentId": environment_id,
            "serviceId": service_id
        }
    })
    
    domain_url = f"https://{data['serviceDomainCreate']['domain']}" if (data and "serviceDomainCreate" in data) else "در حال آماده‌سازی..."
    
    return {
        "project_name": project_name,
        "domain": domain_url,
        "user": "admin",
        "pass": "admin"
    }, None