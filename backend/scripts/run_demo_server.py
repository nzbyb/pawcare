"""Run the dedicated mock server with explicit Python environment overrides."""
import os

# Import sets explicit empty values too. PowerShell removes empty env variables,
# which otherwise allows secrets from the main .env to re-enter BaseSettings.
import prepare_demo  # noqa: F401

os.environ['REDIS_URL'] = ''
os.environ['CORS_ORIGINS'] = 'http://localhost:5174,http://127.0.0.1:5174'

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8001)
