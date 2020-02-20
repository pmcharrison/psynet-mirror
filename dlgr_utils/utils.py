def get_api_arg(arguments: dict, desired: str, use_default = False, default = None):
    if arguments is None:
        if use_default:
            return default
        else:
            raise APIMissingJSON
    elif desired not in arguments:
        if use_default:
            return default
        else:
            raise APIArgumentError
    return arguments[desired]

class APIArgumentError(ValueError):
    pass

class APIMissingJSON(ValueError):
    pass
