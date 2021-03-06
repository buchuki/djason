import base
from django.utils.encoding import smart_unicode, is_protected_type
from django.core.serializers.python import Deserializer as PythonDeserializer
from django.db import models
class Serializer(base.Serializer):

    def __init__(self, *args, **kwargs):
        """
        Initialize instance attributes.
        """
        self._fields = None
        self._extras = None
        self.objects = []
        super(Serializer, self).__init__(*args, **kwargs)

    def start_serialization(self):
        """
        Called when serializing of the queryset starts.
        """
        self._fields = None
        self._extras = None
        self.objects = []

    def end_serialization(self):
        """
        Called when serializing of the queryset ends.
        """
        pass

    def start_object(self, obj):
        """
        Called when serializing of an object starts.
        """
        self._fields = {}
        self._extras = {}

    def end_object(self, obj):
        """
        Called when serializing of an object ends.
        """
        dict_object = dict(self._fields)
        dict_object['model'] = smart_unicode(obj._meta)
        dict_object['pk'] = smart_unicode(obj._get_pk_val(), strings_only=True)
        dict_object.update(self._extras)
        self.objects.append(dict_object)

    def handle_field(self, obj, field):
        """
        Called to handle each individual (non-relational) field on an object.
        """
        value = field._get_val_from_obj(obj)
        # Protected types (i.e., primitives like None, numbers, dates,
        # and Decimals) are passed through as is. All other values are
        # converted to string first.
        if is_protected_type(value):
            self._fields[field.name] = value
        else:
            self._fields[field.name] = field.value_to_string(obj)

    def handle_fk_field(self, obj, field):
        """
        Called to handle a ForeignKey field.
        Recursively serializes relations specified in the 'relations' option.
        """
        fname = field.name
        related = getattr(obj, fname)
        if related is not None:
            if fname in self.relations:
                # perform full serialization of FK
                serializer = Serializer()
                options = {}
                if isinstance(self.relations, dict):
                    if isinstance(self.relations[fname], dict):
                        options = self.relations[fname]
                self._fields[fname] = serializer.serialize([related],
                    **options)[0]
            else:
                # emulate the original behaviour and serialize the pk value
                if self.use_natural_keys and hasattr(related, 'natural_key'):
                    related = related.natural_key()
                else:
                    if field.rel.field_name == related._meta.pk.name:
                        # Related to remote object via primary key
                        related = related._get_pk_val()
                    else:
                        # Related to remote object via other field
                        related = smart_unicode(getattr(related,
                            field.rel.field_name), strings_only=True)
                self._fields[fname] = related
        else:
            self._fields[fname] = smart_unicode(related, strings_only=True)

    def handle_m2m_field(self, obj, field):
        """
        Called to handle a ManyToManyField.
        Recursively serializes relations specified in the 'relations' option.
        """
        if field.rel.through._meta.auto_created:
            fname = field.name
            if fname in self.relations:
                # perform full serialization of M2M
                serializer = Serializer()
                options = {}
                if isinstance(self.relations, dict):
                    if isinstance(self.relations[fname], dict):
                        options = self.relations[fname]
                self._fields[fname] = [
                    serializer.serialize([related], **options)[0]
                       for related in getattr(obj, fname).iterator()]
            else:
                # emulate the original behaviour and serialize to a list of
                # primary key values
                if self.use_natural_keys and hasattr(field.rel.to, 'natural_key'):
                    m2m_value = lambda value: value.natural_key()
                else:
                    m2m_value = lambda value: smart_unicode(
                        value._get_pk_val(), strings_only=True)
                self._fields[fname] = [m2m_value(related)
                    for related in getattr(obj, fname).iterator()]

    def getvalue(self):
        """
        Return the fully serialized queryset (or None if the output stream is
        not seekable).
        """
        return self.objects

    def handle_related_m2m_field(self, obj, field_name):
        """Called to handle 'reverse' m2m RelatedObjects
        Recursively serializes relations specified in the 'relations' option.
        """
        fname = field_name

        if field_name in self.relations:
            # perform full serialization of M2M
            serializer = Serializer()
            options = {}
            if isinstance(self.relations, dict):
                if isinstance(self.relations[field_name], dict):
                    options = self.relations[field_name]
            self._fields[fname] = [
                serializer.serialize([related], **options)[0]
                   for related in getattr(obj, fname).iterator()]
        else:
            pass
            # we don't really want to do this to reverse relations unless
            # explicitly requested in relations option
            #
            # emulate the original behaviour and serialize to a list of ids
            # self._fields[fname] = [
            # smart_unicode(related._get_pk_val(), strings_only=True)
            # for related in getattr(obj, fname).iterator()]

    def handle_related_fk_field(self, obj, field_name):
        """Called to handle 'reverse' fk serialization.
        Recursively serializes relations specified in the 'relations' option.
        """
        fname = field_name
        related = getattr(obj, fname)
        if related is not None:
            if field_name in self.relations:
                # perform full serialization of FK
                serializer = Serializer()
                options = {}
                if isinstance(self.relations, dict):
                    if isinstance(self.relations[field_name], dict):
                        options = self.relations[field_name]
                # Handle reverse foreign key lookups that recurse on the model
                if isinstance(related, models.Manager):
                    # Related fields arrive here as querysets not modelfields
                    self._fields[fname] = serializer.serialize(related.all(),
                        **options)
                else:
                    self._fields[fname] = serializer.serialize([related],
                        **options)[0]
            else:
                pass
                # we don't really want to do this to reverse relations unless
                # explicitly requested in relations option
                #
                # emulate the original behaviour and serialize to a list of ids
                # self._fields[fname] = [
                # smart_unicode(related._get_pk_val(), strings_only=True)
                # for related in getattr(obj, fname).iterator()]
        else:
            self._fields[fname] = smart_unicode(related, strings_only=True)


    def handle_extra_field(self, obj, field):
        """
        Return "extra" fields that the user specifies.
        Can be a property or callable that takes no arguments.
        """
        if hasattr(obj, field):
            extra = getattr(obj, field)
            if callable(extra):
                extra = extra()
            if isinstance(extra, models.query.QuerySet):
                serializer = Serializer()
                options = {}
                if isinstance(self.extras, dict):
                    if isinstance(self.extras[field], dict):
                        options = self.extras[field]
                self._extras[field] = serializer.serialize(extra, **options)
            else:
                self._extras[field] = smart_unicode(extra, strings_only=True)


Deserializer = PythonDeserializer
