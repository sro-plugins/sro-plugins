import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Get from environment variable or use the default provided by user
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:OWEvioxorCxurIx2zYJ8DawLPkZRPCmZb6M4THys6rgH62gi6YowAj5jOfwS5IC0@76.13.141.75:5432/postgres")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
