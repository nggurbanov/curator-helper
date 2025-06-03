# app/handlers/__init__.py
"""
Initializes the handlers package and aggregates routers.
- Imports Router instances from admin.py and user.py.
- Can be used to create a main router that includes all command and message handlers.
"""
from aiogram import Router

from . import user
from . import admin

# You can create a main router here to include all other routers
# This helps in organizing if you have many handler modules.
# For a simpler setup, you might register admin_router and user_router directly in main.py.

# Example of aggregating routers:
# all_handlers_router = Router(name="all_handlers")
# all_handlers_router.include_router(admin.admin_router)
# all_handlers_router.include_router(user.user_router)

# Or, just make them available for individual registration in main.py
admin_router = admin.router
user_router = user.router

__all__ = [
    "admin_router",
    "user_router",
    # "all_handlers_router", # if using the aggregated router approach
]

