import httpx
import time
import logging

logging.basicConfig(filename='scraper_errors.log', level=logging.ERROR)

class ImageCompressionService:
    def __init__(self):
        self.api_url = "https://api.resmush.it/ws.php"
        self.headers = {
            "User-Agent": "AboutBlankScraper/1.0",
            "Referer": "https://about---blank.com"
        }
        self.quality = 90
        self.compressed_urls = {}
        
    def compress_image(self, image_url: str) -> str | None:
        if not image_url:
            return None
            
        if image_url in self.compressed_urls:
            return self.compressed_urls[image_url]
        
        try:
            time.sleep(0.3)
            
            params = {
                "img": image_url,
                "qlty": self.quality
            }
            
            response = httpx.get(
                self.api_url, 
                params=params, 
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("dest"):
                    self.compressed_urls[image_url] = data["dest"]
                    return data["dest"]
                elif data.get("error"):
                    logging.error(f"Compression error for {image_url}: {data.get('error')}")
            else:
                logging.error(f"HTTP error {response.status_code} for {image_url}")
                
        except Exception as e:
            logging.error(f"Failed to compress {image_url}: {e}")
            
        return None
    
    def compress_batch(self, image_urls: list[str]) -> dict[str, str]:
        results = {}
        for url in image_urls:
            if url:
                compressed = self.compress_image(url)
                if compressed:
                    results[url] = compressed
        return results