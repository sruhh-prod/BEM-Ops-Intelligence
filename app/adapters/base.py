"""
Base adapter interface.

Every data source — Hostaway, Breezeway, or any future system — implements
this interface. The sync pipeline calls only these methods and never touches
a source API directly. Swapping sources means swapping adapter instances.

Return contract
---------------
Each method returns a list of dicts. Dict keys match our Supabase column names
exactly, with two exceptions:

  _property_ref   dict  Used by the pipeline to resolve property_id.
                        Must contain one of:
                          {'hostaway_id': int}
                          {'breezeway_id': int}
                        The pipeline strips this key before DB insert.

  _assignee_ids   list  List of breezeway_id ints for task assignees.
                        The pipeline resolves to person UUIDs and writes
                        task_assignments rows. Stripped before task insert.

Adapters never write to the database. That is the pipeline's job.
"""

from __future__ import annotations


from abc import ABC, abstractmethod


class BaseAdapter(ABC):

    @abstractmethod
    def source_name(self) -> str:
        """
        Human-readable identifier written to sync_log.source.
        Use 'hostaway', 'breezeway', or 'mock_breezeway'.
        """

    @abstractmethod
    def get_properties(self) -> list[dict]:
        """
        Return property records normalized to the `properties` table schema.
        Include _property_ref only if the adapter is not the properties source
        (i.e., Breezeway would include it to cross-reference Hostaway).
        """

    @abstractmethod
    def get_reservations(self) -> list[dict]:
        """
        Return reservation records normalized to the `reservations` table schema.
        Each record must include _property_ref for pipeline resolution.
        """

    @abstractmethod
    def get_people(self) -> list[dict]:
        """
        Return staff records normalized to the `people` table schema.
        """

    @abstractmethod
    def get_tasks(self) -> list[dict]:
        """
        Return task records normalized to the `tasks` table schema.
        Each record must include _property_ref and optionally _assignee_ids.
        """

    @abstractmethod
    def get_task_comments(self) -> list[dict]:
        """
        Return all task comment records normalized to `task_comments`.
        Each must include _task_ref: {'breezeway_task_id': int}.
        The pipeline resolves to task UUID before insert.
        """
