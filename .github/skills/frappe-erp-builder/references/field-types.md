# Frappe Field Types Reference

## Text Fields
| Type | Use Case | Options |
|------|----------|---------|
| `Data` | Short text, single line (max 255) | `options: "Email"/"Phone"/"URL"/"Name"/"Barcode"` for validation |
| `Small Text` | 1-2 line text, no formatting | — |
| `Text` | Multi-line plain text | — |
| `Long Text` | Large plain text blocks | — |
| `Text Editor` | Rich text / HTML content | — |
| `Code` | Code snippets with syntax highlight | `options: "Python"/"JavaScript"/"HTML"/"JSON"` |
| `Markdown Editor` | Markdown input | — |
| `HTML` | Static HTML display only | — |

## Numeric Fields
| Type | Use Case | Notes |
|------|----------|-------|
| `Int` | Whole numbers | |
| `Float` | Decimal numbers | Set `precision` |
| `Currency` | Money values | Uses company currency; set `options: "currency"` for multi-currency |
| `Percent` | Percentage 0-100 | Stored as float |
| `Rating` | Star rating 1-5 | |

## Date/Time Fields
| Type | Notes |
|------|-------|
| `Date` | YYYY-MM-DD |
| `Time` | HH:MM:SS |
| `Datetime` | YYYY-MM-DD HH:MM:SS |
| `Duration` | Stored in seconds, shown as "1 hour 30 mins" |

## Choice Fields
| Type | Use Case | Options |
|------|----------|---------|
| `Select` | Fixed dropdown list | `options`: newline-separated values |
| `Check` | Boolean checkbox | Stored as 0/1 |
| `Color` | Color picker | — |
| `Icon` | Icon picker | — |
| `Rating` | Star rating | — |

## Relational Fields
| Type | Use Case | Options |
|------|----------|---------|
| `Link` | FK to another DocType | `options: "DocType Name"` |
| `Dynamic Link` | FK where target DocType comes from another field | `options: "fieldname_that_holds_doctype"` |
| `Table` | Embeds child DocType as rows | `options: "Child DocType Name"` |
| `Table MultiSelect` | Multi-select from a child table | `options: "Child DocType Name"` |

## File Fields
| Type | Notes |
|------|-------|
| `Attach` | File attachment link |
| `Attach Image` | Image attachment, shown inline |
| `Image` | Displays an image from a URL or attachment field |

## Layout Fields (no data stored)
| Type | Use Case |
|------|----------|
| `Section Break` | Creates a new section with optional heading |
| `Column Break` | Splits current section into columns |
| `Tab Break` | Creates a tab |
| `Fold` | Collapses below fields |
| `Heading` | Bold heading text inline |

## Special Fields
| Type | Use Case |
|------|----------|
| `Signature` | Captures a drawn signature |
| `Geolocation` | Stores lat/lng as GeoJSON |
| `Barcode` | Barcode display |
| `Password` | Encrypted text input |
| `Read Only` | Computed/display-only field |
| `Button` | Clickable button (fires JS event) |

## Auto-populated System Fields (always present, don't add manually)
- `name` — Document ID / primary key
- `owner` — Created by (User)
- `creation` — Created datetime
- `modified` — Last modified datetime
- `modified_by` — Last modified by (User)
- `docstatus` — 0=Draft, 1=Submitted, 2=Cancelled
- `idx` — Row index (in child tables)
- `parent`, `parenttype`, `parentfield` — (in child tables)

## Field Option Patterns

### Link field with filter
```javascript
// In JS controller
frm.set_query("item_code", "items", function(frm, cdt, cdn) {
    return {
        filters: {
            "is_stock_item": 1,
            "disabled": 0
        }
    };
});
```

### Select with dynamic options
```python
# In Python controller
def get_select_options():
    return "\n".join(["Option A", "Option B", "Option C"])
```

### Currency field linked to company currency
```json
{
    "fieldname": "amount",
    "fieldtype": "Currency",
    "options": "currency"
}
```
