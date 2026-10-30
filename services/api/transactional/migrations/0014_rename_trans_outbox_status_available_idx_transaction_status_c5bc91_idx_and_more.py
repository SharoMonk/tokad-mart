"""Reconcile legacy outbox index names with Django-generated names.

Some development databases already have the target index names because of
an earlier migration history. Verify the existing definition before treating
the rename as complete; never drop/recreate a working index.
"""
from django.db import migrations


class RenameIndexIfNeeded(migrations.RenameIndex):
    """Accept databases renamed by the historical, removed 0011 migration."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if not self.allow_migrate_model(schema_editor.connection.alias, model):
            return
        with schema_editor.connection.cursor() as cursor:
            indexes = schema_editor.connection.introspection.get_constraints(
                cursor, model._meta.db_table
            )
        if self.old_name not in indexes and self.new_name in indexes:
            index = to_state.models[app_label, self.model_name_lower].get_index_by_name(
                self.new_name
            )
            columns = [model._meta.get_field(field).column for field in index.fields]
            existing = indexes[self.new_name]
            if not existing["index"] or existing["columns"] != columns or existing["unique"]:
                raise ValueError(f"Existing index {self.new_name} has an unexpected definition")
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    dependencies = [
        ("transactional", "0013_product_barcode"),
    ]

    operations = [
        RenameIndexIfNeeded(
            model_name="outboxevent",
            new_name="transaction_status_c5bc91_idx",
            old_name="trans_outbox_status_available_idx",
        ),
        RenameIndexIfNeeded(
            model_name="outboxevent",
            new_name="transaction_aggrega_c37442_idx",
            old_name="trans_outbox_aggregate_idx",
        ),
    ]
