import os
import httpx
from supabase import create_client, ClientOptions
from dotenv import load_dotenv

load_dotenv()

_http1 = httpx.Client(http2=False, timeout=60, follow_redirects=True)

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    options=ClientOptions(httpx_client=_http1),
)