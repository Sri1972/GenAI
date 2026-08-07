# Sample Data & Metadata Files

This directory contains ready-to-use sample files demonstrating the NLP to Structured Data system.

## Directory Structure

```
samples/
├── csv/
│   ├── sales_data.csv                    # Sales transaction data
│   └── sales_data.metadata.json          # CSV metadata with business rules
├── json/
│   ├── products_catalog.json             # Product catalog with ratings
│   └── products_catalog.metadata.json    # JSON schema and validation
└── excel/
    ├── employee_performance.csv          # Employee performance data (Excel format as CSV)
    └── employee_performance.metadata.json # Excel metadata with formulas
```

## How to Use

1. **Download Files**: Right-click and save any file you need
2. **Copy to Your Project**: Place data files in your `data/` directory and metadata files in your `metadata/` directory
3. **Test with MCP Client**: Use these files to test the system functionality

## Sample Queries

### For Sales Data (CSV)
- "Show me the top 5 customers by revenue"
- "Compare Alice Johnson and Bob Wilson's sales performance"
- "Generate an executive summary of Q4 sales"

### For Products Catalog (JSON)
- "Show me all software products as a table"
- "Which products have the highest ratings?"
- "Compare enterprise vs SMB products"

### For Employee Performance (Excel/CSV)
- "Who are the top performers this quarter?"
- "Show department performance summary"
- "Which employees exceeded their targets?"

## File Formats

- **CSV Files**: Standard comma-separated values with headers
- **JSON Files**: Well-structured JSON with nested objects and arrays
- **Excel Files**: Provided as CSV for easy viewing (metadata describes Excel structure)
- **Metadata Files**: JSON format with comprehensive schema, business rules, and validation

## Notes

- All sample data is fictional and for demonstration purposes only
- Metadata files demonstrate best practices for data documentation
- Files are designed to work seamlessly with the MCP system