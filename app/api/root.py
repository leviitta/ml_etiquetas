from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/robots.txt", include_in_schema=False, response_class=PlainTextResponse)
async def robots_txt():
    return "User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: https://www.meliops.cl/sitemap.xml"

@router.get("/sitemap.xml", include_in_schema=False, response_class=PlainTextResponse)
async def sitemap_xml():
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.meliops.cl/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://www.meliops.cl/faq</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""

@router.get("/faq", response_class=HTMLResponse, include_in_schema=False)
async def get_faq(request: Request):
    """Render the FAQ page at a clean, public URL"""
    user = request.session.get('user')
    return templates.TemplateResponse(
        request=request,
        name="faq.html",
        context={"user": user}
    )
