"""
Self-built safeguards for this app, deliberately structured so each concern
lives behind one small module with one stable function signature — routers
never call a specific vendor/library directly. Upgrading any single concern
to a paid provider later means rewriting the inside of that one module and
flipping one env var, never touching the ~50 routers that use it. See each
module's own docstring for its current implementation and its documented
swap-in point.
"""
