
def clean_instance(instance, model):
    if instance and model:
        if isinstance(instance, model):
            return instance
        else:
            try:
                return model.objects.get(id=instance)
            except:
                return None
    else:
        return None


def pdf_base64encode(pdf_filename):
    return open(pdf_filename, "rb").read().encode("base64")
