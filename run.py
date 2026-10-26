import uvicorn

LOCAL_HOST: str = "127.0.0.1"
LOCAL_PORT: int = 8000

if __name__ == "__main__":
    uvicorn.run(
        app="redis_enterprise_services.app:create_app", factory=True, host=LOCAL_HOST, port=LOCAL_PORT
    )
