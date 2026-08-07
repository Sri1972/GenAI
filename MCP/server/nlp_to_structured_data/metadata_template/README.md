# Metadata Templates Guide

This folder contains comprehensive metadata templates for different data formats. These templates enable the Enhanced MCP Server to provide intelligent, context-aware data analysis with **metadata-driven column aliases**.

## 📋 Available Templates

| Template | File | Purpose |
|----------|------|---------|
| **Universal** | `universal_metadata_template.json` | Complete template with all possible fields - works for any data format |
| **CSV** | `csv_metadata_template.json` | Optimized for CSV files with CSV-specific settings |
| **Excel** | `excel_metadata_template.json` | Optimized for Excel/XLSX files with Excel-specific settings |
| **JSON** | `json_metadata_template.json` | Optimized for JSON files with JSON-specific settings |

## 🚀 Quick Start

### 1. Choose Your Template
```bash
# For CSV files
cp csv_metadata_template.json sales_data_metadata.json

# For Excel files  
cp excel_metadata_template.json report_metadata.json

# For JSON files
cp json_metadata_template.json api_data_metadata.json

# For any format (most comprehensive)
cp universal_metadata_template.json my_data_metadata.json
```

### 2. Customize for Your Data
1. Remove the `_template_info` section
2. Update the basic information (title, description, author, etc.)
3. Define your columns in the `data_dictionary.columns` section
4. **Configure column aliases** for natural language queries
5. Set up business rules and data quality requirements

### 3. Place the Metadata File
The system will auto-discover metadata files placed in these locations:
```
# Same directory as data file
data.csv + data_metadata.json
data.xlsx + data_metadata.json

# Metadata subdirectory
data/sales.csv + metadata/sales.json
data/report.xlsx + metadata/excel/report.json

# Type-specific subdirectory
data/info.json + metadata/json/info.json
```

## 🎯 Key Features

### Column Aliases for Natural Language Queries
The most powerful feature is the **aliases** configuration that enables natural language queries:

```json
{
  "SalesRep": {
    "description": "Sales representative name",
    "business_meaning": "Sales rep for commission tracking",
    "aliases": [
      "sales rep",
      "sales representative", 
      "rep",
      "salesperson",
      "agent",
      "sales agent"
    ]
  }
}
```

**This enables queries like:**
- ✅ "show top sales reps"
- ✅ "list agents with highest revenue"  
- ✅ "group by sales representative"
- ✅ "find best performing reps"

### Complete Metadata Structure
Each template includes:

- **📝 Basic Information**: Title, description, version, author
- **🔗 Source Info**: Origin, update frequency, data freshness
- **⚙️ Format-Specific Settings**: CSV delimiters, Excel sheets, JSON structure
- **📊 Data Dictionary**: Column definitions with types, constraints, and **aliases**
- **📋 Business Rules**: Validation, transformation, and processing rules
- **✅ Data Quality**: Completeness, accuracy, consistency requirements
- **🔒 Security**: Data sensitivity, PII, retention policies
- **📈 Analytics Context**: Use cases, metrics, reporting integration

## 📖 Template Details

### Universal Template
- **Best for**: Any data format, maximum flexibility
- **Features**: All possible metadata fields
- **Use when**: You need comprehensive metadata coverage

### CSV Template  
- **Best for**: CSV files with delimited data
- **Features**: CSV parsing settings, encoding, delimiters
- **Use when**: Working with CSV exports, data extracts

### Excel Template
- **Best for**: Excel/XLSX workbooks
- **Features**: Sheet selection, cell ranges, Excel formatting
- **Use when**: Working with Excel reports, manual data entry

### JSON Template
- **Best for**: JSON data files or API responses
- **Features**: JSON structure, nested fields, array handling
- **Use when**: Working with API data, JSON exports

## 🔧 Column Definition Examples

### Basic Column with Aliases
```json
{
  "CustomerName": {
    "description": "Customer company or individual name",
    "type": "string",
    "business_meaning": "Legal entity name for billing",
    "examples": ["Acme Corp", "John Smith"],
    "aliases": [
      "customer name",
      "client name", 
      "company name",
      "customer",
      "client"
    ]
  }
}
```

### Numeric Column with Constraints
```json
{
  "TotalAmount": {
    "description": "Total transaction amount",
    "type": "float",
    "format": "Currency with 2 decimal places",
    "constraints": {
      "required": true,
      "min_value": 0.01
    },
    "business_meaning": "Total value for financial reporting",
    "examples": [99.99, 1500.00, 25.50],
    "aliases": [
      "total amount",
      "amount",
      "total", 
      "revenue",
      "value",
      "price"
    ]
  }
}
```

### Date Column
```json
{
  "TransactionDate": {
    "description": "Date of the transaction",
    "type": "date",
    "format": "YYYY-MM-DD",
    "constraints": {
      "required": true
    },
    "business_meaning": "Transaction date for revenue recognition",
    "examples": ["2024-10-25", "2024-10-24"],
    "aliases": [
      "transaction date",
      "date",
      "timestamp",
      "event date"
    ]
  }
}
```

### Categorical Column
```json
{
  "Status": {
    "description": "Current status of the record",
    "type": "category",
    "constraints": {
      "required": true,
      "allowed_values": ["Active", "Pending", "Completed", "Cancelled"]
    },
    "business_meaning": "Processing status for workflow",
    "examples": ["Active", "Pending"],
    "aliases": [
      "status",
      "state", 
      "condition",
      "phase"
    ]
  }
}
```

## 🎨 Best Practices

### 1. Comprehensive Aliases
Include multiple ways users might refer to columns:
- **Formal terms**: "sales representative"
- **Informal terms**: "sales rep"
- **Abbreviations**: "rep"
- **Domain terms**: "agent"
- **Variants**: "salesperson"

### 2. Clear Business Meaning
Always include `business_meaning` to explain what the column represents in business terms.

### 3. Realistic Examples
Provide actual examples that users will recognize from their data.

### 4. Proper Constraints
Define data validation rules that match your actual data quality requirements.

### 5. Regular Updates
Keep metadata current as data structures evolve.

## 🧪 Testing Your Metadata

### 1. Load and Verify
```python
# Test metadata loading
python test_metadata_debugging.py
```

### 2. Test Aliases
```python
# Test column alias matching
python test_mcp_aliases.py
```

### 3. Interactive Testing
```bash
# Start interactive client
python nlp_to_structured_data_chat_client.py --interactive

# Commands to test:
/load your_data.csv csv your_metadata.json
/aliases
list top sales reps
show highest revenue by agent
```

## 🔄 Metadata Workflow

1. **📋 Copy Template**: Choose appropriate template for your data format
2. **✏️ Customize**: Update all sections with your specific information
3. **🏷️ Define Aliases**: Configure natural language column references
4. **📍 Place File**: Put metadata file where auto-discovery can find it
5. **🧪 Test**: Verify aliases work with sample queries
6. **🔄 Iterate**: Refine based on user feedback and usage patterns

## 🎯 Results

With proper metadata configuration, users can ask natural language questions:
- "show top 3 sales agents with highest revenue"
- "list customers by total amount"
- "group transactions by rep"
- "find agents with most sales"

All of these work seamlessly through the **metadata-driven alias system**!

## 📞 Support

For questions about metadata templates:
1. Check the examples in each template
2. Review the comprehensive documentation
3. Test with the provided debugging tools
4. Use the `/aliases` command to verify configuration