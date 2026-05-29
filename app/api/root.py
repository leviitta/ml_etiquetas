from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, RedirectResponse

router = APIRouter()

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
</urlset>"""

@router.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/api/v1/")
