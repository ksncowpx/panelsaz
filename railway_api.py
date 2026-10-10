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
            if "errors" in data and data["errors"]:
                return None, data["errors"][0]["message"]
            return data.get("data"), None

# بررسی اعتبار توکن و گرفتن آیدی ورک‌اسپیس
async def validate_railway_token(token: str):
    query = """
    query {
        me {
            id
            email
            workspaces {
                id
                name
            }
        }
    }
    """
    data, error = await execute_graphql(token, query)
    if error or not data or not data.get("me"):
        return False, "توکن نامعتبر است یا منقضی شده است."
    return True, data["me"]["email"]

# ساخت پروژه و دیپلوی خودکار پابلو پنل
async def deploy_pablo(token: str):
    # ۱. دریافت اطلاعات اکانت و شناسه Workspace
    user_info_query = """
    query {
        me {
            id
            workspaces {
                id
            }
        }
    }
    """
    user_data, err = await execute_graphql(token, user_info_query)
    if err or not user_data or not user_data.get("me"):
        return None, "خطا در دریافت اطلاعات کاربر از ریلوی."

    workspaces = user_data["me"].get("workspaces", [])
    workspace_id = workspaces[0]["id"] if workspaces else None

    # ۲. ساخت پروژه جدید با ورک‌اسپیس
    rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    project_name = f"pablo-{rand_str}"

    project_input = {"name": project_name}
    if workspace_id:
        project_input["workspaceId"] = workspace_id

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
    data, err = await execute_graphql(token, create_project_query, {"input": project_input})
    if err: 
        return None, f"خطا در ساخت پروژه: {err}"
    
    project_id = data["projectCreate"]["id"]
    environment_id = data["projectCreate"]["environments"]["edges"][0]["node"]["id"]

    # ۳. اتصال و دیپلوی سورس‌کد گیت‌هاب پابلو پنل
    create_service_query = """
    mutation serviceCreate($input: ServiceCreateInput!) {
        serviceCreate(input: $input) {
            id
        }
    }
    """
    service_data, err = await execute_graphql(token, create_service_query, {
        "input": {
            "projectId": project_id,
            "source": {"repo": GITHUB_REPO}
        }
    })
    if err: 
        return None, f"خطا در ایجاد سرویس: {err}"
    
    service_id = service_data["serviceCreate"]["id"]

    # چند ثانیه صبر برای آماده‌سازی اولیه سرور
    await asyncio.sleep(4)

    # ۴. ساخت خودکار دامنه اختصاصی (Generate Domain)
    create_domain_query = """
    mutation serviceDomainCreate($input: ServiceDomainCreateInput!) {
        serviceDomainCreate(input: $input) {
            domain
        }
    }
    """
    domain_data, _ = await execute_graphql(token, create_domain_query, {
        "input": {
            "environmentId": environment_id,
            "serviceId": service_id
        }
    })
    
    domain_url = f"https://{domain_data['serviceDomainCreate']['domain']}" if (domain_data and "serviceDomainCreate" in domain_data) else "دامنه به زودی در داشبورد ریلوی فعال می‌شود"
    
    return {
        "project_name": project_name,
        "domain": domain_url,
        "user": "admin",
        "pass": "admin"
    }, None
