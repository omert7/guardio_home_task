# Setting up ngrok for Pokemon Streaming Proxy

## Installation

1. Download ngrok from [https://ngrok.com/download](https://ngrok.com/download)
2. Extract the zip file to a location of your choice
3. Create a free ngrok account and get your authtoken from the dashboard

## Configuration

1. Authenticate your ngrok client (only needed once):
```
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

## Usage

1. Start your Pokemon Streaming Proxy service (make sure it's running on port 5000):
```
python run.py
```

2. In a separate terminal window, start ngrok to expose your service:
```
ngrok http 5000
```

3. Ngrok will display a URL that looks like `https://xxxx-xx-xx-xxx-xx.ngrok.io`
   This is your publicly accessible hostname.

4. Use this URL in your Guardio stream-start request:
```json
{
  "url": "https://xxxx-xx-xx-xxx-xx.ngrok.io/stream",
  "email": "test@guard.io",
  "enc_secret": "6Jf1bBHYv7QNSWJU8+xrDvkKLBrtbmgcE1ryqoR7mUU="
}
```

## Notes

- The free tier of ngrok provides randomly generated URLs that change every time you restart ngrok
- Ngrok provides a web interface at http://localhost:4040 to inspect all traffic going through your tunnel
- Your local service must be running before starting ngrok 