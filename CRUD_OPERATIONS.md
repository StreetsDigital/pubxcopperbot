# Full CRUD Operations Guide

This bot provides complete Create, Read, Update, and Delete operations for all Copper CRM entities with approval workflows.

## Overview

All CRM modifications (Create, Update, Delete) require approval from designated approvers before being executed.

### Supported Entities
- **People/Contacts**
- **Companies**
- **Opportunities/Deals**
- **Leads**
- **Tasks**
- **Projects**

## READ Operations

### Natural Language Queries

Query any entity type using natural language:

```
Find contacts at Acme Corp
Show me companies in San Francisco
List opportunities over $50,000
Search for tasks due this week
Show me all active projects
```

### Slash Command

```
/copper [your natural language query]
```

### Supported Entity Types in Queries
- People/Contacts: "person", "people", "contact", "contacts"
- Companies: "company", "companies", "organization", "business"
- Opportunities: "opportunity", "opportunities", "deal", "deals", "sale", "sales"
- Leads: "lead", "leads", "prospect", "prospects"
- Tasks: "task", "tasks", "todo", "to-do"
- Projects: "project", "projects"

## CREATE Operations

Create new records in Copper CRM with approval.

### Command Format

```
/copper-create [entity_type] field=value field2=value2
```

### Examples

**Create a Person/Contact:**
```
/copper-create person name="John Smith" email=john@example.com phone=555-1234
```

**Create a Company:**
```
/copper-create company name="Acme Corporation" city="San Francisco" state=CA email_domain=acme.com
```

**Create an Opportunity:**
```
/copper-create opportunity name="Q1 Enterprise Deal" monetary_value=75000 primary_contact_id=12345
```

**Create a Lead:**
```
/copper-create lead name="Jane Doe" email=jane@example.com company_name="Tech Startup"
```

**Create a Task:**
```
/copper-create task name="Follow up with client" due_date=2025-12-01 priority=high
```

**Create a Project:**
```
/copper-create project name="Website Redesign" status=active assignee_id=67890
```

### Common Fields

**Person:**
- `name` (required)
- `email` or `emails`
- `phone` or `phone_numbers`
- `company_id` (link to company)
- `title` (job title)
- `city`, `state`, `country`

**Company:**
- `name` (required)
- `email_domain`
- `phone` or `phone_numbers`
- `city`, `state`, `postal_code`, `country`
- `details` (description)

**Opportunity:**
- `name` (required)
- `monetary_value` (amount)
- `primary_contact_id` (person ID)
- `company_id`
- `status`
- `close_date`

**Lead:**
- `name` (required)
- `email`
- `phone`
- `company_name`
- `status`

**Task:**
- `name` (required)
- `due_date` (YYYY-MM-DD format)
- `priority` (high, medium, low)
- `assignee_id` (user ID)
- `status`

**Project:**
- `name` (required)
- `status` (active, completed, etc.)
- `assignee_id` (user ID)

## UPDATE Operations

Update existing records in Copper CRM with approval.

### Command Format

```
/copper-update [entity_type] [entity_id] field=value field2=value2
```

### Examples

**Update a Person:**
```
/copper-update person 12345 email=newemail@company.com phone=555-9876
```

**Update a Company:**
```
/copper-update company 67890 name="New Company Name" city=Seattle state=WA
```

**Update an Opportunity:**
```
/copper-update opportunity 11111 monetary_value=150000 status=won
```

**Update a Lead:**
```
/copper-update lead 22222 status=qualified email=updated@example.com
```

**Update a Task:**
```
/copper-update task 33333 status=completed
```

**Update a Project:**
```
/copper-update project 44444 status=completed
```

## DELETE Operations

Delete records from Copper CRM with approval (⚠️ **Permanent deletion!**).

### Command Format

```
/copper-delete [entity_type] [entity_id]
```

### Examples

**Delete a Person:**
```
/copper-delete person 12345
```

**Delete a Company:**
```
/copper-delete company 67890
```

**Delete an Opportunity:**
```
/copper-delete opportunity 11111
```

**Delete a Lead:**
```
/copper-delete lead 22222
```

**Delete a Task:**
```
/copper-delete task 33333
```

**Delete a Project:**
```
/copper-delete project 44444
```

### ⚠️ **Important Delete Notes**

- Deletions are **permanent** and cannot be undone
- Always requires approver confirmation
- The entity must exist (bot will verify before creating request)
- Approvers see a clear warning about permanent deletion

## Approval Workflow

All Create, Update, and Delete operations follow this workflow:

### 1. Request Submission

User submits a request via slash command:
- `/copper-create` for creating new records
- `/copper-update` for modifying existing records
- `/copper-delete` for deleting records

### 2. Approval Notification

All designated approvers receive a DM with:
- Operation type (Create/Update/Delete)
- Entity details
- Requested changes or data
- Approve/Reject buttons

### 3. Approver Decision

Approver clicks either:
- **✅ Approve** - Executes the operation in Copper CRM
- **❌ Reject** - Cancels the request

### 4. Execution & Notification

If approved:
- Operation is immediately executed in Copper
- Requester receives confirmation DM
- For creates: Returns new record ID
- For deletes: Confirms deletion
- For updates: Confirms changes applied

If rejected:
- Request is cancelled
- Requester is notified of rejection

## Managing Approvers

### Add an Approver

```
/copper-add-approver @username
```

or

```
/copper-add-approver USER_ID
```

### View Pending Requests

Approvers can view all pending requests:

```
/copper-pending
```

## Advanced Features

### CSV Enrichment

Upload a CSV file to check if records exist in CRM:
- Returns enriched CSV with three new columns
- "Contact is in CRM" (Yes/No)
- "Company is in CRM" (Yes/No)
- "Opportunity exists" (Yes/No)

### Related Items

Query related items for any entity:
```
Show me all tasks for company 12345
Find projects related to opportunity 67890
```

## Best Practices

### For Create Operations

1. **Always include required fields** (usually `name`)
2. **Use quotes for values with spaces**: `name="John Smith"`
3. **Link entities when possible**: Use IDs to connect people to companies, opportunities to contacts, etc.
4. **Verify IDs before linking**: Make sure referenced entities exist

### For Update Operations

1. **Only update fields that need changing**
2. **Get the entity ID first** using a search query
3. **Double-check IDs** before submitting requests
4. **Be specific** about what you're changing

### For Delete Operations

1. **Always verify you have the correct ID**
2. **Export or backup data** if needed before deletion
3. **Consider archiving** instead of deleting (use status updates)
4. **Be absolutely certain** - deletions are permanent!

### For Approvers

1. **Review carefully** before approving
2. **Check for typos** in create/update data
3. **Verify entity IDs** in update/delete requests
4. **Question suspicious requests** (e.g., bulk deletions)
5. **For deletes**: Confirm the entity should really be removed

## Security Notes

- **All destructive operations require approval**
- **Only designated users can approve**
- **All operations are logged**
- **No direct writes** - everything goes through approval workflow
- **Approvers should be trusted team members**

## Troubleshooting

### "Request not found"
- The request ID may have expired
- Use `/copper-pending` to see active requests

### "Could not find entity with ID"
- The entity doesn't exist in Copper
- Verify the ID using a search query first

### "Missing required field"
- Check which fields are required for that entity type
- Refer to the Common Fields section above

### "Failed to create/update/delete"
- Check Copper API connection
- Verify permissions on the API key
- Ensure rate limits aren't exceeded (180 req/min)

## Quick Reference

| Operation | Command | Example |
|-----------|---------|---------|
| **Search** | `/copper [query]` | `/copper Find contacts at Microsoft` |
| **Create** | `/copper-create [type] field=value` | `/copper-create person name="John" email=john@example.com` |
| **Update** | `/copper-update [type] [id] field=value` | `/copper-update person 123 email=newemail@company.com` |
| **Delete** | `/copper-delete [type] [id]` | `/copper-delete person 123` |
| **Add Approver** | `/copper-add-approver @user` | `/copper-add-approver @manager` |
| **View Pending** | `/copper-pending` | `/copper-pending` |

## API Coverage

This bot provides full CRUD access to:

✅ **People/Contacts** - Create, Read, Update, Delete
✅ **Companies** - Create, Read, Update, Delete
✅ **Opportunities** - Create, Read, Update, Delete
✅ **Leads** - Create, Read, Update, Delete
✅ **Tasks** - Create, Read, Update, Delete
✅ **Projects** - Create, Read, Update, Delete
✅ **Activities** - Read only
✅ **Related Items** - Read relationships between entities

All operations respect Copper's rate limit of 180 requests per minute.
