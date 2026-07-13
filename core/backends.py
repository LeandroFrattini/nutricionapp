"""
Backend de autenticación que deja iniciar sesión con el nombre de usuario O
el email indistintamente — así nadie queda trabado por no acordarse cuál de
los dos eligió al registrarse (o al crear una cuenta desde el panel).
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

UserModel = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = UserModel.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
