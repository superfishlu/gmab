# gmab/utils/naming.py

import random
import string

def generate_random_string(length=12):
    """Generate a random string of lowercase letters and digits."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def make_label(prefix="gmab", length=12):
    """Generate a unique gmab instance label, e.g. 'gmab-3ul7u0p1x9ns'."""
    return f"{prefix}-{generate_random_string(length)}"
