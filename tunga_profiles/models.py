from __future__ import unicode_literals

import uuid

import tagulous.models
from django.db import models
from django_countries.fields import CountryField
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga_profiles.validators import validate_email
from tunga_utils.constants import REQUEST_STATUS_INITIAL, REQUEST_STATUS_ACCEPTED, REQUEST_STATUS_REJECTED
from tunga_utils.models import AbstractExperience


class Skill(tagulous.models.TagModel):
    class TagMeta:
        initial = "PHP, JavaScript, Python, Ruby, Java, C#, C++, Ruby, Swift, Objective C, .NET, ASP.NET, Node.js," \
                  "HTML, CSS, HTML5, CSS3, XML, JSON, YAML," \
                  "Django, Ruby on Rails, Flask, Yii, Lavarel, Express.js, Spring, JAX-RS," \
                  "AngularJS, React.js, Meteor.js, Ember.js, Backbone.js," \
                  "WordPress, Joomla, Drupal," \
                  "jQuery, jQuery UI, Bootstrap, AJAX," \
                  "Android, iOS, Windows Mobile, Apache Cordova, Ionic," \
                  "SQL, MySQL, PostgreSQL, MongoDB, CouchDB," \
                  "Git, Subversion, Mercurial, " \
                  "Docker, Ansible, " \
                  "Webpack, Grunt, Gulp, Ant, Maven, Gradle"


class City(tagulous.models.TagModel):
    class TagMeta:
        initial = "Kampala, Entebbe, Jinja, Nairobi, Mombosa, Dar es Salaam, Kigali, Amsterdam"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    country = CountryField(blank=True, null=True)
    city = tagulous.models.SingleTagField(to=City, blank=True, null=True)
    street = models.CharField(max_length=100, blank=True, null=True)
    plot_number = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.IntegerField(blank=True, null=True)
    postal_address = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    company = models.CharField(max_length=200, blank=True, null=True)
    skills = tagulous.models.TagField(to=Skill, blank=True)
    website = models.URLField(blank=True, null=True)

    def __unicode__(self):
        return self.user.get_short_name()

    @property
    def city_name(self):
        return str(self.city)

    @property
    def country_name(self):
        return self.country.name

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


class SocialPlatform(models.Model):
    name = models.CharField(max_length=100, unique=True)
    url_prefix = models.CharField(max_length=200, blank=True, null=True)
    placeholder = models.CharField(max_length=100, blank=True, null=True)
    icon = models.URLField(blank=True, null=True)
    fa_icon = models.CharField(max_length=20, blank=True, null=True)
    glyphicon = models.CharField(max_length=20, blank=True, null=True)
    created_by = models.ForeignKey(
            settings.AUTH_USER_MODEL, related_name='social_platforms_created', on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return False

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return False


class SocialLink(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    platform = models.ForeignKey(SocialPlatform)
    link = models.URLField(blank=True, null=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s -  %s' % (self.user.get_short_name(), self.platform)

    class Meta:
        unique_together = ('user', 'platform')

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


class Education(AbstractExperience):
    institution = models.CharField(max_length=200)
    award = models.CharField(max_length=200)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name, self.institution)

    class Meta:
        verbose_name_plural = 'education'


class Work(AbstractExperience):
    company = models.CharField(max_length=200)
    position = models.CharField(max_length=200)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name, self.company)

    class Meta:
        verbose_name_plural = 'work'


class Connection(models.Model):
    from_user = models.ForeignKey(
            settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='connections_initiated')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='connection_requests')
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s -> %s' % (self.from_user.get_short_name, self.to_user.get_short_name)

    class Meta:
        ordering = ['-created_at']

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.from_user or request.user == self.to_user

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.from_user or request.user == self.to_user


APPLICATION_STATUS_CHOICES = (
    (REQUEST_STATUS_INITIAL, 'Received'),
    (REQUEST_STATUS_ACCEPTED, 'Accepted'),
    (REQUEST_STATUS_REJECTED, 'Rejected')
)


class DeveloperApplication(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(unique=True, validators=[validate_email])
    phone_number = models.CharField(max_length=15)
    country = CountryField()
    city = models.CharField(max_length=50)
    stack = models.TextField()
    experience = models.TextField()
    discovery_story = models.TextField()
    status = models.PositiveSmallIntegerField(
            choices=APPLICATION_STATUS_CHOICES,
            help_text=','.join(['%s - %s' % (item[0], item[1]) for item in APPLICATION_STATUS_CHOICES]),
            default=REQUEST_STATUS_INITIAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmation_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    confirmation_sent_at = models.DateTimeField(blank=True, null=True, editable=False)
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(blank=True, null=True, editable=False)

    def __unicode__(self):
        return self.display_name

    @property
    def display_name(self):
        return '%s %s' % (self.first_name, self.last_name)

    @property
    def country_name(self):
        return self.country.name
    country_name.fget.short_description = 'country'
