# GeoLite2 database (not committed)

The worker geolocates clicks with MaxMind's free **GeoLite2-City** database.

1. Create a free account at https://www.maxmind.com/en/geolite2/signup
2. Download *GeoLite2 City* (`.mmdb` format)
3. Save it here as `backend/data/GeoLite2-City.mmdb`

docker-compose mounts this folder read-only into the api and worker containers.
Without the file, everything still works, and country/city show as "Unknown".
