# Quick Start: Using Metadata Templates

This guide will get you using metadata templates in **under 5 minutes**.

## ⚡ Super Quick Setup

### Step 1: Copy a Template (30 seconds)
```bash
# Navigate to metadata template folder
cd "d:\SourceCode\GenAI\MCP\server\nlp_to_structured_data\metadata_template"

# Copy the template that matches your data:
copy csv_metadata_template.json my_sales_data_metadata.json
```

### Step 2: Basic Customization (2 minutes)
Edit `my_sales_data_metadata.json`:

1. **Remove template info** (lines 2-12)
2. **Update basic info**:
```json
{
  "title": "My Sales Data",
  "description": "Monthly sales performance data",
  "author": "Your Name"
}
```

3. **Configure your columns** in `data_dictionary.columns`:
```json
{
  "data_dictionary": {
    "columns": {
      "SalesRep": {
        "description": "Sales representative name",
        "type": "string",
        "aliases": ["sales rep", "rep", "agent", "salesperson"]
      },
      "Amount": {
        "description": "Sale amount",
        "type": "float", 
        "aliases": ["amount", "total", "revenue", "value"]
      }
    }
  }
}
```

### Step 3: Place the File (30 seconds)
Put your metadata file next to your data:
```
sales_data.csv
my_sales_data_metadata.json  ← Same folder
```

### Step 4: Test It! (1 minute)
```bash
# Start the client
python nlp_to_structured_data_chat_client.py --interactive

# Load your data
/load sales_data.csv csv my_sales_data_metadata.json

# Check your aliases work
/aliases

# Try natural queries
show top sales reps by revenue
list agents with highest amounts
```

## 🎯 Most Important: Column Aliases

The **key feature** is the `aliases` array in each column definition:

```json
{
  "CustomerName": {
    "aliases": [
      "customer name",    ← Formal
      "customer",         ← Short
      "client name",      ← Alternative
      "client"            ← Business term
    ]
  }
}
```

**This enables natural queries like:**
- ✅ "group by customer name"
- ✅ "show top clients" 
- ✅ "list by customer"
- ✅ "group by client name"

## 🏃‍♂️ Working Example

Here's a complete minimal metadata file for sales data:

```json
{
  "title": "Sales Performance Data",
  "description": "Monthly sales tracking",
  "version": "1.0",
  "author": "Sales Team",
  
  "source_information": {
    "origin": "CRM Export",
    "format": "CSV"
  },
  
  "format_specific": {
    "csv": {
      "delimiter": ",",
      "header_row": 1,
      "encoding": "utf-8"
    }
  },
  
  "data_dictionary": {
    "columns": {
      "SalesRep": {
        "description": "Sales representative name",
        "type": "string",
        "business_meaning": "Sales rep for commission tracking",
        "aliases": ["sales rep", "rep", "agent", "salesperson", "sales agent"]
      },
      "CustomerName": {
        "description": "Customer company name", 
        "type": "string",
        "business_meaning": "Customer for sales attribution",
        "aliases": ["customer name", "customer", "client", "company"]
      },
      "TotalAmount": {
        "description": "Total sale amount",
        "type": "float",
        "business_meaning": "Revenue for reporting",
        "aliases": ["total amount", "amount", "total", "revenue", "value", "price"]
      },
      "SaleDate": {
        "description": "Date of sale",
        "type": "date", 
        "business_meaning": "Sale date for time-based analysis",
        "aliases": ["sale date", "date", "transaction date", "timestamp"]
      }
    }
  }
}
```

Save this as `sales_metadata.json` and you're ready to go!

## 🔥 Pro Tips

1. **Include many aliases** - users will refer to columns in different ways
2. **Use business terms** - include domain-specific language your users know
3. **Test your aliases** - use `/aliases` command to verify they're working
4. **Start simple** - you can always add more metadata fields later

## 🚨 Common Mistakes to Avoid

❌ **Don't forget to remove `_template_info`**
❌ **Don't skip the aliases arrays** 
❌ **Don't use technical column names in aliases** - use business terms
❌ **Don't place metadata file in wrong location**

✅ **Do include multiple ways to say the same thing**
✅ **Do use terms your users actually say**
✅ **Do test with real queries**
✅ **Do start with the template that matches your format**

## 🎉 You're Done!

That's it! Your metadata-driven column aliases are now working. Users can ask natural language questions and the system will intelligently map their terms to your actual columns.

**Next steps:**
- Add more detailed business rules
- Include data quality requirements  
- Configure advanced format settings
- Share the metadata with your team

Happy querying! 🚀