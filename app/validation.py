class Validation:
    def validate_post(self,body):
        keys = dict(body).keys()
        for key in keys:
            value = body[key]
            if(value is None):
                del body[key]
        return dict(body)