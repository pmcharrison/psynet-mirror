import random

hsl_dimensions = [
    {
        "name": "hue",
        "min_value": 0,
        "max_value": 360
    },
    {
        "name": "saturation",
        "min_value": 0,
        "max_value": 100
    },
    {
        "name": "lightness",
        "min_value": 0,
        "max_value": 100
    },
]

def random_hsl_sample(i):
    min_value = hsl_dimensions[i]["min_value"]
    max_value = hsl_dimensions[i]["max_value"]
    return random.randint(min_value, max_value)