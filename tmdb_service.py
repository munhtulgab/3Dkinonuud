"""
=============================================
  TMDB API Сервис
  Киноны мэдээллийг TMDB-ээс татах
=============================================
"""

import httpx
import logging

logger = logging.getLogger(__name__)

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


class TMDBService:
    """TMDB API-тай харилцах сервис"""

    def __init__(self, api_key: str, base_url: str = "https://api.themoviedb.org/3"):
        self.api_key = api_key
        self.base_url = base_url

    async def fetch_movie(self, tmdb_id: int) -> dict:
        """
        TMDB-ээс киноны мэдээлэл татах.
        
        Args:
            tmdb_id: TMDB дахь киноны ID (жишээ: 550 = Fight Club)
            
        Returns:
            dict: Киноны мэдээлэл (title, overview, poster_path, ...)
        """
        url = f"{self.base_url}/movie/{tmdb_id}"
        params = {
            "api_key": self.api_key,
            "language": "en-US"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                # Жанрууд
                genres = [g["name"] for g in data.get("genres", [])]

                # Poster URL бүтээх
                poster_path = data.get("poster_path", "")
                backdrop_path = data.get("backdrop_path", "")

                movie = {
                    "tmdb_id": data["id"],
                    "title": data.get("title", "Unknown"),
                    "original_title": data.get("original_title", ""),
                    "overview": data.get("overview", ""),
                    "poster_path": f"{TMDB_IMAGE_BASE}/w500{poster_path}" if poster_path else "",
                    "backdrop_path": f"{TMDB_IMAGE_BASE}/w1280{backdrop_path}" if backdrop_path else "",
                    "vote_average": round(data.get("vote_average", 0), 1),
                    "release_date": data.get("release_date", ""),
                    "genres": genres,
                    "runtime": data.get("runtime", 0),
                }

                logger.info(f"✅ TMDB киноны мэдээлэл татлаа: {movie['title']} (ID: {tmdb_id})")
                return movie

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"⚠️  TMDB ID {tmdb_id} олдсонгүй")
                raise Exception(f"TMDB ID {tmdb_id} бүхий кино олдсонгүй")
            logger.error(f"❌ TMDB алдаа: {e.response.status_code}")
            raise Exception(f"TMDB API алдаа: {e.response.status_code}")
        except Exception as e:
            logger.error(f"❌ TMDB алдаа: {str(e)}")
            raise

    async def search_movies(self, query: str, page: int = 1) -> dict:
        """
        TMDB-ээс кино хайх.
        
        Args:
            query: Хайх текст
            page: Хуудас
            
        Returns:
            dict: {results: list, total_pages: int, total_results: int}
        """
        url = f"{self.base_url}/search/movie"
        params = {
            "api_key": self.api_key,
            "query": query,
            "page": page,
            "language": "en-US"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("results", []):
                    poster = item.get("poster_path", "")
                    results.append({
                        "tmdb_id": item["id"],
                        "title": item.get("title", ""),
                        "overview": item.get("overview", "")[:200],
                        "poster_path": f"{TMDB_IMAGE_BASE}/w200{poster}" if poster else "",
                        "vote_average": round(item.get("vote_average", 0), 1),
                        "release_date": item.get("release_date", ""),
                    })

                return {
                    "results": results,
                    "total_pages": data.get("total_pages", 0),
                    "total_results": data.get("total_results", 0),
                }

        except Exception as e:
            logger.error(f"❌ TMDB хайлт алдаа: {str(e)}")
            raise
