import asyncio
import httpx

async def main():
    try:
        async with httpx.AsyncClient() as wc:
            loc = "London"
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={loc}&count=1&language=en&format=json"
            geo_res = await wc.get(geo_url, timeout=3.0)
            data = geo_res.json()
            if "results" in data:
                lat = data["results"][0]["latitude"]
                lon = data["results"][0]["longitude"]
                country = data["results"][0].get("country", "")
                
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                w_res = await wc.get(weather_url, timeout=3.0)
                cw = w_res.json().get("current_weather", {})
                
                print(f"Weather in {loc}, {country}: {cw.get('temperature')}°C, Wind {cw.get('windspeed')} km/h")
            else:
                print("Location not found.")
    except Exception as e:
        print(f"Error: {repr(e)}")

asyncio.run(main())
