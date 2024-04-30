# DO NOT EDIT. This file was generated with:
#
# $ gen-schema-mixins

"""Type definitions for generated methods on schema classes"""

from typing import cast, TYPE_CHECKING
if TYPE_CHECKING:
    from edb.schema import schema as s_schema
from edb.schema import orm as s_orm
from edb.schema import objects
from edb.schema import triggers
from edb.schema import objtypes
from edb.schema import policies


class ObjectTypeRefMixinMixin:

    def get_access_policies(
        self, schema: 's_schema.Schema'
    ) -> 'objects.ObjectIndexByUnqualifiedName[policies.AccessPolicy]':
        val = s_orm.get_field_value(self, schema, 'access_policies')
        return cast(objects.ObjectIndexByUnqualifiedName[policies.AccessPolicy], val)

    def get_triggers(
        self, schema: 's_schema.Schema'
    ) -> 'objects.ObjectIndexByUnqualifiedName[triggers.Trigger]':
        val = s_orm.get_field_value(self, schema, 'triggers')
        return cast(objects.ObjectIndexByUnqualifiedName[triggers.Trigger], val)


class ObjectTypeMixin:

    def get_union_of(
        self, schema: 's_schema.Schema'
    ) -> 'objects.ObjectSet[objtypes.ObjectType]':
        val = s_orm.get_field_value(self, schema, 'union_of')
        return cast(objects.ObjectSet[objtypes.ObjectType], val)

    def get_intersection_of(
        self, schema: 's_schema.Schema'
    ) -> 'objects.ObjectSet[objtypes.ObjectType]':
        val = s_orm.get_field_value(self, schema, 'intersection_of')
        return cast(objects.ObjectSet[objtypes.ObjectType], val)

    def get_is_opaque_union(
        self, schema: 's_schema.Schema'
    ) -> 'bool':
        val = s_orm.get_field_value(self, schema, 'is_opaque_union')
        return cast(bool, val)
