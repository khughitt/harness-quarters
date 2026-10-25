"""A privacy denylist the session-log fixtures must not match."""
import re

PRIVATE = re.compile(r"/home/|/mnt/|/Users/|Dropbox|keith|titan|europa|@[a-z]+\.(com|org)|toolu_01"
                     r"|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
