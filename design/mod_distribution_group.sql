/*
 * Copyright 2013 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 *
 */

category:metainfo;
name=dlgroup;
category:metainfo;
version=1.0;

/*

  distribution_group

  Additional group attributes related to distribution groups used in
  Exchange. Distribution groups will have a specific naming scheme,
  namely "Dl-"-prefix. Naming scheme is realized through cereconf
  variable "EXCHANGE_DISTRIBUTION_GROUP_PREFIX".

  The relevant API-definition may be found in
  "Cerebrum/modules/exchange/DistributionGroup.py".

  The following values are needed in order to create a
  distribution-group in Exchange:

  - Identity: the name of the group from entity_name
  - Name: the name of the group from entity_name
  - DisplayName: the name vith name_variant = dl_group_displ_name from
    entity_language_name
  - RoomList: distribution group containing room-objects, in which case
    only identity and displayname should be exported to
    Exchange. TODO: should we also export primaryEmailAddress? NB!
    Functionality related to roomlists has low priority and might
    not be implemented at this point (Jazz, 2013-11). Should be
    implemented as a separate command!
  - ManagedBy: contact email address for the person/org. unit tasked
    with developing and maintaining policy for this groups membership
    maintenance, from 'mngdby_addrid', where 'mngdby_addrid' is a
    valid e-mail address in Cerebrum
  - ModerationEnabled: let messages to the group be moderated, default
    = true (API must ensure that enabled moderation requires
    defined moderators), from 'modenable'
  - ModeratedBy: a list of accounts i UiO-domain that may moderate
    messages for this group (required if modenabled = true), from
    varchar 'modby' (API should make sure UiO-AD accounts, and the
    pop requirement with moderationenabled)
  - MemberDepartRestriction: rules for leaving the group in Exchange,
    from 'deprestr'. Valide values: Open, Closed, ApprovalRequired,
    default "Closed", validated database-level
  - MemberJoinRestriction: rules for becoming a member of the group
    in Exchange, from 'joinrestr'. Valide values: Open, Closed,
    ApprovalRequired, default "Closed", validated database-level
  - HiddenFromAddressListEnabled: should the group be made visible
    in Exchange address list, from 'hidden'. Default value = true.
  - PrimarySMTPAddress: email_primary_address_address_id for target
    with target_entity_id = group_id
  - EmailAddresses: list of all valid addresses from email_address for
    target with target_entity_id = group_id
*/

category:main;
CREATE TABLE distribution_group
(
  group_id  NUMERIC(12,0)
        CONSTRAINT distribution_group_pk PRIMARY KEY
        CONSTRAINT distribution_group_group_id
                REFERENCES group_info(group_id),

  roomlist  CHAR (1)
        DEFAULT 'F'
        NOT NULL
        CONSTRAINT distribution_group_roomlist_bool
                CHECK (roomlist IN ('T', 'F')),

  mngdby_addrid  NUMERIC(12,0)
        NOT NULL
        CONSTRAINT email_primary_address_address
                REFERENCES email_address(address_id),

  modenable CHAR (1)
        DEFAULT 'T'
        NOT NULL
        CONSTRAINT distribution_group_modenable_bool
                CHECK (modenable IN ('T', 'F')),

  modby     CHAR VARYING (512),

  deprestr  CHAR VARYING (64)
        DEFAULT 'Closed'
        NOT NULL
        CONSTRAINT distribution_group_deprestr
                CHECK (deprestr IN ('Closed',
                                    'Open',
                                    'ApprovalRequired')),

  joinrestr CHAR VARYING (64)
        DEFAULT 'Closed'
        NOT NULL
        CONSTRAINT distribution_group_joinrestr
                CHECK (joinrestr IN ('Closed',
                                     'Open',
                                     'ApprovalRequired')),

  hidden    CHAR (1)
        DEFAULT 'F'
        NOT NULL
        CONSTRAINT distribution_group_hidden_bool
                CHECK (hidden IN ('T', 'F'))
);

category:drop;
DROP TABLE distribution_group;
