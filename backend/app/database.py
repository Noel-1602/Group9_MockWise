from typing import AsyncGenerator
from app.config import settings

# Check if greenlet and SQLAlchemy are available
USE_ASYNC_ENGINE = False

try:
    import greenlet
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.orm import declarative_base, sessionmaker
    from sqlalchemy import create_engine

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False}
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )

    sync_engine = create_engine(
        settings.SYNC_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

    SyncSessionLocal = sessionmaker(
        bind=sync_engine,
        autocommit=False,
        autoflush=False
    )

    Base = declarative_base()
    USE_ASYNC_ENGINE = True

except (ImportError, ModuleNotFoundError):
    try:
        from sqlalchemy.orm import declarative_base, sessionmaker
        from sqlalchemy import create_engine

        sync_engine = create_engine(
            settings.SYNC_DATABASE_URL,
            connect_args={"check_same_thread": False}
        )

        SyncSessionLocal = sessionmaker(
            bind=sync_engine,
            autocommit=False,
            autoflush=False
        )

        Base = declarative_base()
        engine = None
        AsyncSessionLocal = None

        class AsyncSessionSyncAdapter:
            """
            Adapter wrapping standard synchronous SQLAlchemy session to provide
            an async interface when greenlet library is unavailable.
            """
            def __init__(self, sync_session):
                self.sync_session = sync_session

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    self.sync_session.rollback()
                self.sync_session.close()

            def add(self, instance):
                self.sync_session.add(instance)

            def add_all(self, instances):
                self.sync_session.add_all(instances)

            async def commit(self):
                self.sync_session.commit()

            async def rollback(self):
                self.sync_session.rollback()

            async def close(self):
                self.sync_session.close()

            async def refresh(self, instance, attribute_names=None, with_for_update=None):
                self.sync_session.refresh(instance, attribute_names=attribute_names)

            async def flush(self, objects=None):
                self.sync_session.flush(objects=objects)

            async def execute(self, statement, params=None, execution_options=None, bind_arguments=None, **kw):
                return self.sync_session.execute(statement, params=params, execution_options=execution_options, bind_arguments=bind_arguments, **kw)

            async def scalar(self, statement, params=None, execution_options=None, bind_arguments=None, **kw):
                return self.sync_session.scalar(statement, params=params, execution_options=execution_options, bind_arguments=bind_arguments, **kw)

            async def delete(self, instance):
                self.sync_session.delete(instance)

    except (ImportError, ModuleNotFoundError):
        # Pure Python fallback shim when running without SQLAlchemy installed
        Base = object
        engine = None
        sync_engine = None
        AsyncSessionLocal = None
        SyncSessionLocal = None
        AsyncSessionSyncAdapter = None


async def get_db() -> AsyncGenerator:
    if USE_ASYNC_ENGINE:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    elif SyncSessionLocal is not None:
        async with AsyncSessionSyncAdapter(SyncSessionLocal()) as session:
            try:
                yield session
            finally:
                await session.close()
    else:
        yield None


async def init_db():
    if USE_ASYNC_ENGINE:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    elif sync_engine is not None and Base is not object:
        Base.metadata.create_all(sync_engine)

