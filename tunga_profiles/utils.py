from tunga_profiles.models import AppIntegration


def profile_check(user):
    if not user.first_name or not user.last_name or not user.email or not user.profile:
        return False

    required = ['country', 'city', 'street', 'plot_number', 'postal_code']

    if user.is_developer:
        required.extend(['payment_method', 'id_document'])
    elif user.is_project_owner:
        required.extend(['company'])

    profile_dict = user.profile.__dict__
    for k, v in profile_dict.iteritems():
        if k in required and not v:
            return False
    return True


def get_app_integration(user, provider):
    try:
        return AppIntegration.objects.filter(user=user, provider=provider).latest('updated_at')
    except AppIntegration.DoesNotExist:
        return None