from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Authenticate a customer by their email address (case-insensitive).

    Registered alongside the default ModelBackend so customers can sign in with
    either their username or their email in the same login form.

    If several accounts share the same email the address is ambiguous, so we
    refuse to authenticate it rather than risk logging into the wrong account;
    those users can still sign in with their username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = UserModel.objects.get(email__iexact=username)
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user
            # (mirrors django.contrib.auth.backends.ModelBackend.authenticate).
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # Ambiguous email shared by several accounts: refuse to guess.
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
