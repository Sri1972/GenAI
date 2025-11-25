# Universal Metadata Schema v2.0

## Overview

The Universal Metadata Schema provides a standardized structure for describing any data source, regardless of format (CSV, Excel, JSON, etc.). It combines comprehensive metadata coverage with format-specific optimizations through a layered architecture.

## Schema Structure

```json
{
  "schema_version": "2.0",
  "created_at": "ISO 8601 timestamp",
  "format": "csv|excel|json|parquet|xml|yaml|tsv",
  
  // Core Information
  "dataset_info": { ... },
  "source_info": { ... },
  
  // Data Structure
  "data_dictionary": { ... },
  
  // Quality & Governance
  "quality_profile": { ... },
  "governance": { ... },
  "security_classification": { ... },
  
  // Context
  "analytics_context": { ... },
  "business_context": { ... },
  
  // Format-Specific
  "format_specific": {
    "csv": { ... },
    "excel": { ... },
    "json": { ... }
  },
  
  // Extensions
  "extensions": { ... },
  
  // Management
  "management": { ... }
}
```

## Detailed Schema

### 1. Core Information

#### dataset_info
```json
{
  "dataset_info": {
    "title": "Human-readable title",
    "description": "Comprehensive description",
    "version": "Semantic version (e.g., 1.2.0)",
    "author": "Data owner/creator",
    "contact": "Contact information",
    "created_date": "YYYY-MM-DD",
    "updated_date": "YYYY-MM-DD",
    "tags": ["domain", "category", "keywords"],
    "language": "en|es|fr|etc",
    "timezone": "UTC|America/New_York|etc"
  }
}
```

#### source_info
```json
{
  "source_info": {
    "origin": "Source system or process description",
    "collection_method": "How data is collected",
    "update_frequency": "daily|weekly|monthly|real-time|on-demand",
    "data_freshness": "How current the data is",
    "data_lineage": "Source systems and transformations",
    "dependencies": ["upstream data sources"],
    "sla": {
      "availability": "99.9%",
      "freshness": "< 24 hours",
      "completeness": "95%"
    }
  }
}
```

### 2. Data Structure

#### data_dictionary
```json
{
  "data_dictionary": {
    "columns": {
      "COLUMN_NAME": {
        "description": "Clear description",
        "type": "string|integer|float|boolean|date|datetime|category|array|object",
        "format": "Specific format (e.g., 'YYYY-MM-DD', 'USD')",
        "position": 1,
        
        "constraints": {
          "required": true,
          "unique": false,
          "min_value": null,
          "max_value": null,
          "min_length": null,
          "max_length": null,
          "pattern": "regex pattern",
          "allowed_values": ["enum", "values"],
          "custom": {"domain_specific": "rules"}
        },
        
        "business_meaning": "What this represents in business terms",
        "examples": ["sample1", "sample2"],
        "aliases": ["alternative names", "business terms"],
        
        "relationships": {
          "foreign_key": "table.column",
          "references": "What this relates to",
          "parent_column": "hierarchical parent",
          "derived_from": ["source columns"]
        },
        
        "quality_metrics": {
          "completeness": 0.95,
          "uniqueness": 0.80,
          "validity": 0.99,
          "accuracy": 0.98
        },
        
        "statistics": {
          "count": 10000,
          "unique_count": 500,
          "null_count": 50,
          "min_value": 0,
          "max_value": 1000,
          "mean": 250.5,
          "median": 230.0,
          "std_dev": 75.2,
          "percentiles": {
            "25": 180.0,
            "75": 320.0,
            "95": 450.0,
            "99": 500.0
          }
        },
        
        "sensitive_data": {
          "is_pii": false,
          "classification": "public|internal|confidential|restricted",
          "masking_rule": "hash|mask|encrypt|none"
        }
      }
    },
    
    "relationships": {
      "primary_keys": ["column1", "column2"],
      "foreign_keys": [
        {
          "columns": ["col1"],
          "references": "other_dataset.column"
        }
      ],
      "hierarchies": [
        {
          "name": "organizational",
          "levels": ["department", "team", "employee"]
        }
      ]
    },
    
    "business_rules": {
      "validation_rules": [
        {
          "rule": "total_amount = sum(line_items)",
          "type": "calculation",
          "severity": "error"
        }
      ],
      "transformation_rules": [
        {
          "rule": "standardize_phone_format",
          "type": "formatting",
          "description": "Format phone numbers as (XXX) XXX-XXXX"
        }
      ],
      "derivation_rules": [
        {
          "target_column": "profit_margin",
          "formula": "(revenue - cost) / revenue",
          "dependencies": ["revenue", "cost"]
        }
      ]
    }
  }
}
```

### 3. Quality & Governance

#### quality_profile
```json
{
  "quality_profile": {
    "overall_score": 0.92,
    "last_assessed": "2024-01-15T10:30:00Z",
    
    "dimensions": {
      "completeness": {
        "score": 0.95,
        "required_fields_complete": 0.98,
        "overall_completeness": 0.93,
        "critical_gaps": ["customer_id missing in 2% of records"]
      },
      "accuracy": {
        "score": 0.91,
        "validation_pass_rate": 0.89,
        "business_rule_compliance": 0.94,
        "reference_data_match": 0.90
      },
      "consistency": {
        "score": 0.88,
        "format_consistency": 0.92,
        "cross_field_consistency": 0.85,
        "temporal_consistency": 0.87
      },
      "timeliness": {
        "score": 0.94,
        "update_frequency_met": true,
        "data_lag_acceptable": true,
        "average_lag_hours": 2.5
      }
    },
    
    "issues": [
      {
        "type": "accuracy",
        "severity": "medium",
        "description": "Invalid email formats in 5% of records",
        "affected_columns": ["email"],
        "suggested_fix": "Apply email validation rule"
      }
    ],
    
    "monitoring": {
      "automated_checks": true,
      "alert_thresholds": {
        "completeness": 0.90,
        "accuracy": 0.85
      },
      "last_check": "2024-01-15T10:30:00Z"
    }
  }
}
```

#### governance
```json
{
  "governance": {
    "data_owner": "Business unit responsible",
    "data_steward": "Technical contact",
    "domain": "sales|finance|hr|operations",
    
    "approval_process": {
      "required": true,
      "approvers": ["data_owner", "compliance_team"],
      "last_approved": "2024-01-01",
      "next_review": "2024-07-01"
    },
    
    "change_management": {
      "change_log_location": "https://wiki.company.com/data-changes",
      "notification_required": true,
      "impact_assessment": "required_for_breaking_changes"
    },
    
    "compliance": {
      "regulations": ["GDPR", "CCPA", "SOX"],
      "retention_policy": "7_years",
      "deletion_schedule": "automated_after_retention",
      "audit_trail": true
    }
  }
}
```

### 4. Context

#### analytics_context
```json
{
  "analytics_context": {
    "primary_use_cases": [
      "sales_performance_analysis",
      "commission_calculation",
      "forecasting"
    ],
    
    "key_metrics": [
      {
        "name": "monthly_revenue",
        "formula": "SUM(total_amount) GROUP BY month",
        "business_importance": "high"
      }
    ],
    
    "reporting_integration": {
      "dashboards": ["executive_dashboard", "sales_dashboard"],
      "reports": ["monthly_sales_report"],
      "frequency": "daily"
    },
    
    "ml_applications": [
      {
        "model": "sales_forecasting",
        "features": ["total_amount", "sales_rep", "customer"],
        "target": "next_month_sales"
      }
    ]
  }
}
```

#### business_context
```json
{
  "business_context": {
    "domain": "sales",
    "business_process": "order_to_cash",
    "stakeholders": ["sales_team", "finance", "executives"],
    
    "kpis": [
      {
        "name": "sales_growth",
        "definition": "YoY revenue increase",
        "target": 0.15,
        "current": 0.12
      }
    ],
    
    "seasonality": {
      "has_seasonal_patterns": true,
      "peak_periods": ["Q4", "holiday_season"],
      "adjustment_factors": {"Q4": 1.3, "Q1": 0.8}
    }
  }
}
```

### 5. Format-Specific

#### CSV Specific
```json
{
  "format_specific": {
    "csv": {
      "delimiter": ",",
      "quote_char": "\"",
      "escape_char": "\\",
      "header_row": 1,
      "skip_rows": 0,
      "encoding": "utf-8",
      "line_terminator": "\\n",
      "date_format": "%Y-%m-%d",
      "decimal_separator": ".",
      "thousands_separator": ",",
      "null_values": ["", "NULL", "null", "N/A"],
      "estimated_size": {
        "rows": 10000,
        "file_size_mb": 2.5
      }
    }
  }
}
```

#### Excel Specific
```json
{
  "format_specific": {
    "excel": {
      "sheet_names": ["Data", "Lookup", "Summary"],
      "default_sheet": "Data",
      "header_row": 1,
      "skip_rows": 0,
      "max_rows": null,
      "use_columns": "A:Z",
      "sheet_specific": {
        "Data": {
          "data_range": "A1:Z10000",
          "has_formulas": false
        },
        "Lookup": {
          "data_range": "A1:B100",
          "purpose": "reference_data"
        }
      }
    }
  }
}
```

#### JSON Specific
```json
{
  "format_specific": {
    "json": {
      "structure": "array_of_objects",
      "encoding": "utf-8",
      "lines": false,
      "date_format": "iso",
      "schema": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"},
          "name": {"type": "string"}
        }
      },
      "nested_fields": {
        "customer.address.city": {
          "type": "string",
          "description": "Customer's city"
        }
      }
    }
  }
}
```

### 6. Extensions & Management

#### extensions
```json
{
  "extensions": {
    "custom_fields": {
      "domain_specific": "Any custom metadata",
      "company_specific": "Company-specific fields"
    },
    "integrations": {
      "data_catalog": "catalog_id_12345",
      "lineage_tool": "lineage_graph_url"
    }
  }
}
```

#### management
```json
{
  "management": {
    "schema_version": "2.0",
    "loaded_at": "2024-01-15T10:30:00Z",
    "saved_at": "2024-01-15T10:30:00Z",
    "source_file": "/path/to/data.csv",
    "metadata_file": "/path/to/metadata.json",
    "auto_detected": false,
    "format": "csv",
    "checksum": "sha256_hash",
    "validation_status": "passed",
    "last_updated_by": "system|user_id"
  }
}
```

## Usage Patterns

### 1. Minimal Metadata
```json
{
  "schema_version": "2.0",
  "dataset_info": {
    "title": "Sales Data",
    "description": "Monthly sales records"
  },
  "data_dictionary": {
    "columns": {
      "sales_rep": {
        "type": "string",
        "aliases": ["rep", "salesperson"]
      },
      "amount": {
        "type": "float", 
        "aliases": ["total", "revenue"]
      }
    }
  }
}
```

### 2. Comprehensive Metadata
Use the full schema with all sections for critical datasets requiring detailed governance and quality monitoring.

### 3. Format-Specific Optimization
Include format-specific sections for optimized processing of different data types.

## Benefits

1. **Universal Compatibility**: Works with any data format
2. **Extensible**: Custom fields via extensions
3. **Layered**: Start minimal, add detail as needed
4. **Standardized**: Consistent structure across all datasets
5. **Business-Focused**: Rich business context and meaning
6. **Quality-Aware**: Built-in quality assessment framework
7. **Governance-Ready**: Comprehensive governance metadata
8. **AI-Friendly**: Perfect for ML pipeline metadata

## Migration Guide

### From Current Templates
1. Map existing fields to universal schema
2. Add auto-detection capabilities
3. Enhance with quality profiles
4. Include governance metadata

### Implementation Strategy
1. Start with minimal schema for new datasets
2. Gradually enhance with quality and governance metadata
3. Use format-specific adapters for optimization
4. Implement auto-discovery for user convenience