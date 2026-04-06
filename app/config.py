from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    airflow_base_url: str = "http://localhost:8080"
    airflow_username: str = "airflow"
    airflow_password: str = "airflow"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
