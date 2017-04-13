from tunga_profiles.models import AppIntegration


def profile_check(user):
    if not user.first_name or not user.last_name or not user.email or not user.profile:
        return False

    required = ['country', 'city', 'street', 'plot_number', 'postal_code']

    if user.is_developer or user.is_project_manager:
        required.extend(['payment_method', 'id_document'])
    # elif user.is_project_owner:
    #    required.extend(['company'])

    profile_dict = user.profile.__dict__
    for key in profile_dict:
        if key in required and not profile_dict[key]:
            return False
    return True


def get_app_integration(user, provider):
    try:
        return AppIntegration.objects.filter(user=user, provider=provider).latest('updated_at')
    except AppIntegration.DoesNotExist:
        return None
