"""Map Werkzueg exceptions to domain specific exceptions

These exceptions should be used in all domain (non-Flask specific) code
to avoid tying in to Flask / Werkzueg where it is not needed.
"""

from werkzeug.exceptions import Forbidden, NotFound, UnprocessableEntity

InvalidPayload = UnprocessableEntity

__all__ = ['NotFound', 'Forbidden', 'InvalidPayload']
