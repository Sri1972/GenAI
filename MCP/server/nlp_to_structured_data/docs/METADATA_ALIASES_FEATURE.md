# Metadata-Driven Column Aliases Feature

## Overview

The Enhanced MCP Server now supports **metadata-driven column aliases** - a configurable approach to column name matching that eliminates hardcoded synonyms and makes column references more flexible and maintainable.

## Benefits

✅ **Configurable**: Column aliases are defined in metadata files, not hardcoded in source code  
✅ **Maintainable**: Easy to add/modify aliases without changing server code  
✅ **User-Friendly**: Natural language queries work with business terms  
✅ **Intelligent**: Priority-based matching (exact → partial → fallback)  
✅ **Transparent**: Detailed debugging shows alias resolution process  

## How It Works

### 1. Metadata Configuration

Add an `aliases` array to any column definition in your metadata file:

```json
{
  "data_dictionary": {
    "columns": {
      "SalesRep": {
        "description": "Sales representative name",
        "type": "string",
        "business_meaning": "Sales rep for commission tracking",
        "aliases": [
          "sales rep",
          "sales representative", 
          "rep",
          "salesperson",
          "sales person",
          "agent",
          "sales agent"
        ]
      },
      "TotalAmount": {
        "description": "Total sale amount",
        "type": "float",
        "business_meaning": "Total transaction value for financial reporting",
        "aliases": [
          "total amount",
          "amount", 
          "total",
          "total sales",
          "sales amount",
          "revenue",
          "value",
          "transaction amount"
        ]
      }
    }
  }
}
```

### 2. Intelligent Column Matching

The system uses a **priority-based matching algorithm**:

1. **Priority 1: Metadata-driven aliases**
   - Exact alias match: `"sales rep"` → `SalesRep`
   - Partial alias match: `"rep"` → `SalesRep` (via "sales rep")

2. **Priority 2: Direct column name matching**
   - Exact column name: `"SalesRep"` → `SalesRep`
   - Compound word matching: `"sales rep"` → `SalesRep`

3. **Priority 3: Fallback partial matching**
   - Traditional partial matching for backward compatibility

### 3. Natural Language Queries

Users can now ask questions using business terminology:

```
✅ "list the top 2 amounts for each sales rep"
✅ "show customers with highest revenue" 
✅ "find agents with most sales"
✅ "group by sales representative"
```

All of these work seamlessly with the configured aliases!

## Implementation Details

### Enhanced `_find_column()` Method

The core column matching logic now:

```python
def _find_column(self, search_terms: list, exclude_terms: list = None) -> str:
    # Priority 1: Metadata-driven alias matching
    if self.column_definitions:
        for actual_column, column_info in self.column_definitions.items():
            aliases = column_info.get('aliases', [])
            for alias in aliases:
                if search_phrase == alias.lower():  # Exact match
                    return actual_column
                if search_phrase in alias.lower():  # Partial match
                    return actual_column
    
    # Priority 2: Direct column name matching
    # Priority 3: Fallback partial matching
    # ...
```

### New MCP Tools

#### `list_column_aliases`
Shows all available column aliases from metadata:

```python
# Via MCP tool
await session.call_tool("list_column_aliases", {})

# Via client command  
/aliases
```

**Output:**
```
📋 Available Column Aliases:

**CustomerID** (Primary customer identifier):
  Aliases: 'customer id', 'cust id', 'customer identifier', 'client id'

**SalesRep** (Sales rep for commission tracking):  
  Aliases: 'sales rep', 'sales representative', 'rep', 'salesperson'
  
💡 Usage: You can refer to any column using its name or aliases in queries.
```

## Debugging & Transparency

The system provides detailed debugging output showing the alias resolution process:

```
DEBUG: Searching for column with phrase: 'sales rep'
DEBUG: EXACT alias match: 'sales rep' -> 'SalesRep' via alias 'sales rep'
DEBUG: Group column found: SalesRep for 'sales rep'
```

## Configuration Examples

### Sales Data Aliases
```json
{
  "CustomerID": {
    "aliases": ["customer id", "cust id", "customer identifier", "client id", "account id"]
  },
  "CustomerName": {
    "aliases": ["customer name", "client name", "company name", "account name", "customer", "client"]
  },
  "TotalAmount": {
    "aliases": ["total amount", "amount", "total", "revenue", "value", "transaction amount"]
  },
  "SalesRep": {
    "aliases": ["sales rep", "sales representative", "rep", "salesperson", "agent", "sales agent"]
  }
}
```

### HR Data Aliases
```json
{
  "EmployeeID": {
    "aliases": ["employee id", "emp id", "staff id", "worker id"]
  },
  "FullName": {
    "aliases": ["full name", "name", "employee name", "staff name"]
  },
  "Salary": {
    "aliases": ["salary", "pay", "compensation", "wage", "income"]
  },
  "Department": {
    "aliases": ["department", "dept", "division", "team", "unit"]
  }
}
```

## Migration from Hardcoded Synonyms

**Before** (hardcoded in code):
```python
# Fixed synonyms in code
metric_mappings = {
    'amount': ['amount', 'total', 'totalamount', 'value'],
    'rep': ['salesrep', 'representative', 'agent']
}
```

**After** (configurable in metadata):
```json
{
  "TotalAmount": {
    "aliases": ["amount", "total", "value", "revenue"]
  },
  "SalesRep": {
    "aliases": ["rep", "representative", "agent", "sales rep"]
  }
}
```

## Best Practices

### 1. Comprehensive Alias Coverage
```json
{
  "SalesRep": {
    "aliases": [
      "sales rep",           // Exact business term
      "sales representative", // Formal version
      "rep",                 // Abbreviation
      "salesperson",         // Alternative term
      "sales person",        // Spaced version
      "agent",               // Generic term
      "sales agent"          // Specific variant
    ]
  }
}
```

### 2. Consider User Vocabulary
- Include both formal and informal terms
- Add abbreviations and acronyms
- Include plural/singular variants
- Consider domain-specific terminology

### 3. Avoid Conflicts
- Ensure aliases are unique across columns
- Use specific rather than generic terms when possible
- Test for ambiguous matches

## Testing

### Command Line Testing
```bash
# Test metadata loading
python test_metadata_debugging.py

# Test MCP tool integration  
python test_mcp_aliases.py
```

### Interactive Testing
```bash
# Start client with metadata
python nlp_to_structured_data_chat_client.py --interactive

# Commands to test:
/load D:/data/sales.csv csv D:/metadata/sales.metadata.json
/aliases
list top 2 amounts for each sales rep
show agents with highest revenue
```

## Future Enhancements

1. **Auto-suggestion**: Suggest aliases when column not found
2. **Fuzzy matching**: Handle typos in alias matching
3. **Contextual aliases**: Different aliases for different query contexts
4. **Alias validation**: Detect and warn about conflicting aliases
5. **Alias analytics**: Track which aliases are used most frequently

## Summary

The metadata-driven column aliases feature transforms the MCP server from having **hardcoded synonyms** to a **flexible, configurable system** that:

- ✅ Moves configuration out of code into metadata
- ✅ Enables natural language queries with business terms
- ✅ Provides transparent debugging and alias resolution
- ✅ Supports easy maintenance and updates
- ✅ Scales to any domain or data structure

This architectural improvement makes the system more maintainable, user-friendly, and adaptable to different business contexts without requiring code changes.