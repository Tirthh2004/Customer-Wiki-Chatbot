"""
Query Orchestrator - 3-phase LLM pipeline for query generation
"""

import json
import sqlite3
from openai import AzureOpenAI
import config
from validator import SQLValidator

class QueryOrchestrator:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION
        )
        self.validator = SQLValidator()
        self.db_path = config.DATABASE_PATH
        self.schema_context = self._load_schema()
    
    def _load_schema(self):
        """Load schema context"""
        try:
            with open(config.SCHEMA_OUTPUT, 'r') as f:
                return json.load(f)
        except:
            return None
    
    def _create_schema_prompt(self):
        """Create schema description for LLM"""
        if not self.schema_context:
            return "Schema not available. Please run schema_analyzer.py first."
        
        prompt = "DATABASE SCHEMA:\n\n"
        
        # Add business concepts first
        if 'business_concepts' in self.schema_context:
            prompt += "BUSINESS CONCEPTS (use these to answer questions):\n"
            for concept, info in self.schema_context['business_concepts'].items():
                if 'description' in info:  # Only show if description exists
                    prompt += f"\n{concept.upper()}: {info['description']}\n"
                    if 'table' in info:
                        prompt += f"  Table: {info['table']}\n"
                    if 'key_columns' in info:
                        prompt += f"  Key columns: {', '.join(info['key_columns'])}\n"
                    if 'status_column' in info:
                        prompt += f"  Status column: {info['status_column']}\n"
                    if 'important_notes' in info:
                        prompt += f"  IMPORTANT: {info['important_notes']}\n"
                    if 'join_example' in info:
                        prompt += f"  JOIN example: {info['join_example']}\n"
                    if 'stage_order' in info:
                        prompt += "  Stage order (earliest to latest):\n"
                        for stage in info['stage_order']:
                            prompt += f"    {stage['order']}. {stage['stage']} - {stage['meaning']}\n"
                    if 'rules' in info:
                        prompt += "  Rules:\n"
                        for rule in info['rules']:
                            prompt += f"    - {rule}\n"
                elif concept == 'QUERY_PATTERNS' or concept == 'FK_RESOLUTION_RULES':
                    prompt += f"\n{concept}:\n"
                    if 'important_notes' in info:
                        prompt += f"  CRITICAL: {info['important_notes']}\n"
                    for key, val in info.items():
                        if key not in ('description', 'important_notes', 'rules'):
                            if isinstance(val, str):
                                prompt += f"  {key}: {val}\n"
                            elif isinstance(val, list):
                                for item in val:
                                    prompt += f"    - {item}\n"
            prompt += "\n" + "="*60 + "\n\n"
        
        prompt += "TABLES WITH SAMPLE DATA:\n\n"
        
        # Show key tables with sample values
        important_tables = ['Entity_Company', 'entity_contact', 'entityopportunity', 
                           'entity_placement', 'position', 'cases_customer_management',
                           'relay_user']
        
        for table_name in important_tables:
            if table_name in self.schema_context['tables']:
                table_info = self.schema_context['tables'][table_name]
                prompt += f"{table_name} ({table_info['row_count']} rows)\n"
                prompt += "Key Columns:\n"
                
                # Show more columns for key tables (30) to ensure financial/FK columns are visible
                num_cols = 30 if table_name in ('Entity_Company', 'entity_placement', 'entityopportunity', 'relay_user') else 15
                
                # Show first N columns with samples
                for i, (col_name, col_info) in enumerate(list(table_info['columns'].items())[:num_cols]):
                    pk = " [PRIMARY KEY]" if col_info['primary_key'] else ""
                    samples = ""
                    if col_info.get('sample_values') and len(col_info['sample_values']) > 0:
                        samples = f" (examples: {', '.join(str(v) for v in col_info['sample_values'][:2])})"
                    prompt += f"  - {col_name}: {col_info['type']}{pk}{samples}\n"
                
                if len(table_info['columns']) > num_cols:
                    prompt += f"  ... and {len(table_info['columns']) - num_cols} more columns\n"
                prompt += "\n"
        
        # Show other tables briefly
        prompt += "\nOTHER TABLES:\n"
        for table_name in self.schema_context['tables']:
            if table_name not in important_tables:
                table_info = self.schema_context['tables'][table_name]
                prompt += f"  - {table_name} ({table_info['row_count']} rows)\n"
        
        # Show relationships
        if self.schema_context['relationships']:
            prompt += "\n" + "="*60 + "\n"
            prompt += "RELATIONSHIPS:\n"
            for rel in self.schema_context['relationships'][:20]:  # Show first 20
                prompt += f"  {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}\n"
        
        return prompt
    
    def phase1_intent_analysis(self, user_question):
        """Phase 1: Understand user intent"""
        schema_prompt = self._create_schema_prompt()
        
        system_prompt = """You are a SQL expert analyzing business data questions. Your job is to create a detailed query plan.

CRITICAL RULES:
- The person name in relay_user is in column `Preferred_Full_Name` (EXACT column name: `Preferred_Full_Name`).
- RESOURCE_NAME in entity_placement is UNRELIABLE (fabricated per row). To identify or count distinct people, ALWAYS use `RESOURCE_NAME_EXD_OBJECT_ID` as the FK to `relay_user.Entity_ID`.
- All _EXD_OBJECT_ID columns are foreign keys to another table's Entity_ID.
- COMPANY FILTERING RULE: NEVER use exact equality `= 'CompanyName'`. ALWAYS use `LIKE '%CompanyName%'` (e.g. `CUSTOMER_NAME LIKE '%Northwind Energy%'` or `Company_Name LIKE '%Ironwood Logistics%'`) because companies have suffixes like Ltd, LLC, Inc, Corp.
- For financial questions: ARR_AMOUNT and MRR_AMOUNT are in entityopportunity. BILLING_AMOUNT is in entity_placement. Values have commas, use CAST(REPLACE(col, ',', '') AS REAL).
- ARR and MRR are separate financial metrics. When asked for ARR across open opportunities, select BOTH ARR and MRR sums, and COUNT(*). Open opportunities = STATUS = 'Active'.
- For pipeline/stage questions: Use OPPORTUNITY_STAGE with ordering: Discovery(1) → Qualification(2) → Proposal Sent/Proposal(3) → Negotiation(4) → Closed Won(5).
- Always consider whether the question requires JOINs across tables, aggregation (COUNT, SUM, GROUP BY), or FK resolution."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{schema_prompt}\n\nUser Question: {user_question}\n\nAnalyze and identify:\n1. Required tables and JOIN paths (specify which _EXD_OBJECT_ID columns to join on)\n2. Required columns (including any FK columns needed for resolution, e.g. Preferred_Full_Name from relay_user)\n3. Filter conditions (use LIKE '%...%' for company/customer names)\n4. Aggregation needed (COUNT, SUM, GROUP BY, HAVING, ORDER BY)\n5. Does this question require resolving person identity through relay_user?\n6. Does this question involve financial metrics (ARR, MRR, billing)?\n\nProvide a detailed analysis."}
        ]
        
        response = self.client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=config.TEMPERATURE,
            max_tokens=800
        )
        
        return response.choices[0].message.content
    
    def phase2_sql_generation(self, user_question, intent_analysis):
        """Phase 2: Generate SQL query"""
        schema_prompt = self._create_schema_prompt()
        
        system_prompt = """You are a SQL expert generating SQLite queries. Output ONLY the SQL query.

CRITICAL RULES:
1. Generate ONLY ONE SQL query — no multiple queries.
2. Use JOINs when multiple tables are needed. Always join using _EXD_OBJECT_ID = Entity_ID, never match on display name strings.
3. The true person name in relay_user is in column `Preferred_Full_Name`. RESOURCE_NAME in entity_placement is FABRICATED and unreliable. To identify people, JOIN `entity_placement.RESOURCE_NAME_EXD_OBJECT_ID = relay_user.Entity_ID` and select `relay_user.Preferred_Full_Name`.
4. To count distinct people, use `COUNT(DISTINCT RESOURCE_NAME_EXD_OBJECT_ID)`, not `COUNT(DISTINCT RESOURCE_NAME)`.
5. COMPANY MATCHING: NEVER use `= 'CompanyName'`. ALWAYS use `LIKE '%CompanyName%'` (e.g. `ep.CUSTOMER_NAME LIKE '%Northwind Energy%'` or `ec.Company_Name LIKE '%Ironwood Logistics%'` or `eo.OPPORTUNITY_NAME LIKE '%Ironwood Logistics%'`).
6. For company names with opportunities: JOIN `entityopportunity.COMPANY_EXD_OBJECT_ID = Entity_Company.Entity_ID`.
7. ARR_AMOUNT and MRR_AMOUNT are in entityopportunity. BILLING_AMOUNT is in entity_placement. Clean with `CAST(REPLACE(column, ',', '') AS REAL)`.
8. Opportunity stage ordering: Discovery=1, Qualification=2, 'Proposal Sent'=3, 'Proposal'=3, Negotiation=4, 'Closed Won'=5. Use CASE WHEN for sorting.
9. You may use ORDER BY ... LIMIT N for ranking/top-N queries.
10. For all other queries, do NOT use LIMIT — return all matching records.
11. Output ONLY the SQL query — no comments, no markdown, no explanation."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{schema_prompt}\n\nUser Question: {user_question}\n\nIntent Analysis: {intent_analysis}\n\nGenerate a SINGLE SQL query following all the rules above."}
        ]
        
        response = self.client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=config.TEMPERATURE,
            max_tokens=1000
        )
        
        sql_query = response.choices[0].message.content.strip()
        
        # Clean up SQL query - remove markdown and comments
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        # Remove SQL comments
        lines = sql_query.split('\n')
        sql_query = '\n'.join([line for line in lines if not line.strip().startswith('--')])
        
        return sql_query.strip()
    
    def execute_query(self, sql_query):
        """Execute SQL query and return results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(sql_query)
            results = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            conn.close()
            
            return {
                'success': True,
                'columns': columns,
                'data': results,
                'row_count': len(results)
            }
        except Exception as e:
            conn.close()
            return {
                'success': False,
                'error': str(e)
            }
    
    def phase3_format_results(self, user_question, results, sql_query=""):
        """Phase 3: Format results using LLM for intelligent summarization"""
        if not results['success']:
            return f"Error executing query: {results['error']}"
        
        if results['row_count'] == 0:
            return "No records found matching your criteria."
        
        # Build a data summary for the LLM
        data_summary = f"Query returned {results['row_count']} records.\n"
        data_summary += f"Columns: {', '.join(results['columns'])}\n\n"
        
        # Include up to 50 rows for LLM context (enough for accurate summarization)
        max_rows_for_llm = min(50, results['row_count'])
        data_summary += f"Data (showing {max_rows_for_llm} of {results['row_count']} rows):\n"
        for i, row in enumerate(results['data'][:max_rows_for_llm]):
            row_str = " | ".join(f"{col}: {val}" for col, val in zip(results['columns'], row))
            data_summary += f"  Row {i+1}: {row_str}\n"
        
        if results['row_count'] > max_rows_for_llm:
            data_summary += f"\n... and {results['row_count'] - max_rows_for_llm} more records not shown.\n"
        
        # Use LLM for intelligent summarization
        try:
            system_prompt = """You are a business data analyst. Summarize the query results in a clear, natural language response.

Rules:
- Directly answer the user's original question.
- Include specific numbers, counts, percentages, and names from the data.
- If there are aggregated results, present them clearly with totals.
- If there are many rows, highlight the key findings and provide a summary (e.g., top entries, distribution breakdown).
- Format monetary values with $ and commas.
- Be concise but comprehensive — don't leave out important data points.
- If the data shows a table/list, format it nicely with alignment."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Original question: {user_question}\n\nSQL query used: {sql_query}\n\n{data_summary}\n\nProvide a clear, comprehensive answer to the original question based on this data."}
            ]
            
            response = self.client.chat.completions.create(
                model=config.AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                temperature=config.TEMPERATURE,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to basic formatting if LLM call fails
            print(f"  ⚠ LLM summarization failed, using basic format: {e}")
            summary = f"Found {results['row_count']} records.\n\n"
            summary += "Results:\n"
            for i, row in enumerate(results['data'][:10]):
                summary += f"\nRecord {i+1}:\n"
                for col, val in zip(results['columns'], row):
                    summary += f"  {col}: {val}\n"
            if results['row_count'] > 10:
                summary += f"\n... and {results['row_count'] - 10} more records (all data retrieved)"
            return summary
    
    def process_query(self, user_question):
        """Complete 3-phase query processing"""
        print("\n" + "="*60)
        print("Processing Query...")
        print("="*60)
        
        # Phase 1: Intent Analysis
        print("\n[Phase 1] Analyzing intent...")
        intent = self.phase1_intent_analysis(user_question)
        print(f"Intent: {intent[:200]}...")
        
        # Phase 2: SQL Generation
        print("\n[Phase 2] Generating SQL...")
        sql_query = self.phase2_sql_generation(user_question, intent)
        print(f"SQL: {sql_query}")
        
        # Validate SQL
        print("\n[Validation] Checking SQL safety...")
        validation = self.validator.validate_and_check(sql_query)
        
        if not validation['valid']:
            print(f"❌ Validation failed: {validation['errors']}")
            return {
                'success': False,
                'error': f"Query validation failed: {', '.join(validation['errors'])}"
            }
        
        print("✓ SQL is valid and safe")
        
        # Execute Query
        print("\n[Execution] Running query...")
        results = self.execute_query(sql_query)
        
        if not results['success']:
            print(f"❌ Query failed: {results['error']}")
            return results
        
        print(f"✓ Retrieved {results['row_count']} records")
        
        # Phase 3: Format Results
        print("\n[Phase 3] Formatting results...")
        formatted = self.phase3_format_results(user_question, results, sql_query)
        
        print("="*60)
        
        return {
            'success': True,
            'sql_query': sql_query,
            'results': results,
            'formatted_output': formatted
        }

if __name__ == "__main__":
    orchestrator = QueryOrchestrator()
    
    # Test query
    test_question = "Show me all companies"
    result = orchestrator.process_query(test_question)
    
    if result['success']:
        print("\n" + result['formatted_output'])
