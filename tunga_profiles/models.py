from __future__ import unicode_literals

import tagulous.models
from django.db import models
from django_countries.fields import CountryField

from tunga import settings


class Skill(tagulous.models.TagModel):
    class TagMeta:
        initial = "PHP, JavaScript, Python, Ruby, Java, C#, C++, Ruby, Swift, Objective C, .NET, ASP.NET, Node.js," \
                  "HTML, CSS, HTML5, CSS3, XML, JSON, YAML," \
                  "Django, Ruby on Rails, Flask, Yii, Lavarel, Express.js, Spring, JAX-RS" \
                  "AngularJS, React.js, Meteor.js, Ember.js, Backbone.js," \
                  "WordPress, Joomla, Drupal," \
                  "jQuery, jQuery UI, Bootstrap, AJAX," \
                  "Android, iOS, Windows Mobile, Apache Cordova, Ionic," \
                  "SQL, MySQL, PostgreSQL, MongoDB, CouchDB" \
                  "Git, Subversion, Mercurial, " \
                  "Docker, Ansible, " \
                  "Webpack, Grunt, Gulp, Ant, Maven, Gradle"


class City(tagulous.models.TagModel):
    class TagMeta:
        initial = "Kampala, Entebbe, Jinja, Nairobi, Mombosa, Dar es Salaam, Kigali, Amsterdam"


class Institution(tagulous.models.TagModel):
    class TagMeta:
        initial = 'Makerere University'


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True, null=True)
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


class AbstractExperience(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_month = models.PositiveSmallIntegerField()
    start_year = models.PositiveIntegerField()
    end_month = models.PositiveSmallIntegerField(blank=True, null=True)
    end_year = models.PositiveIntegerField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s' % self.user.get_short_name

    class Meta:
        abstract = True


class Education(AbstractExperience):
    institution = tagulous.models.SingleTagField(to=Institution)
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
