from fastapi import FastAPI

app = FastAPI(title="CarSpot API", version="1.0.0")

@app.get("/")
def root():
    return {"message": "CarSpot API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}