"""
Debug specific user questions
"""

import sqlite3
import config

def test_query(description, sql):
    """Execute and display query results"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"SQL: {sql}\n")
    
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        print(f"Rows returned: {len(results)}\n")
        
        if results:
            print("Results:")
            for i, row in enumerate(results[:10]):
                print(f"\nRow {i+1}:")
                for col, val in zip(columns, row):
                    if val is not None and val != '':
                        print(f"  {col}: {val}")
        else:
            print("NO RESULTS FOUND!")
            print("\nLet me check what data exists...")
        
        conn.close()
        return len(results)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return 0

print("\n" + "="*60)
print("DEBUGGING USER QUESTIONS")
print("="*60)

# Question 1: TAG-7319 opportunity
print("\n\nQUESTION 1: Give me information about TAG-7319 opportunity")
result = test_query(
    "Search for TAG-7319 in opportunities",
    "SELECT * FROM entityopportunity WHERE OPPORTUNITY_NAME LIKE '%TAG-7319%' OR Entity_ID = 'TAG-7319' OR COMPANY LIKE '%TAG-7319%'"
)

if result == 0:
    print("\n🔍 Checking if TAG-7319 exists anywhere...")
    test_query(
        "Search ALL columns for TAG-7319",
        "SELECT Entity_ID, OPPORTUNITY_NAME, COMPANY, OPPORTUNITY_STAGE, STATUS FROM entityopportunity WHERE CAST(Entity_ID AS TEXT) = 'TAG-7319'"
    )
    
    # Check sample opportunity IDs
    test_query(
        "Show sample opportunity Entity_IDs",
        "SELECT Entity_ID, OPPORTUNITY_NAME FROM entityopportunity LIMIT 5"
    )

# Question 2: Northwind Logistics
print("\n\nQUESTION 2: What's going on with Northwind Logistics?")
result = test_query(
    "Search for Northwind Logistics",
    "SELECT Company_Name, Company_Status, Industry FROM Entity_Company WHERE Company_Name LIKE '%Northwind Logistics%'"
)

if result > 0:
    print("\n🔍 Now getting all related data...")
    
    # Get opportunities for Northwind
    test_query(
        "Opportunities for Northwind",
        """SELECT o.OPPORTUNITY_NAME, o.OPPORTUNITY_STAGE, o.STATUS 
           FROM entityopportunity o
           JOIN Entity_Company c ON o.COMPANY_EXD_OBJECT_ID = c.Entity_ID
           WHERE c.Company_Name LIKE '%Northwind Logistics%'
           LIMIT 5"""
    )
    
    # Get contacts for Northwind
    test_query(
        "Contacts for Northwind",
        "SELECT FULL_NAME, TITLE, EMAIL_ADDRESS FROM entity_contact WHERE COMPANY LIKE '%Northwind Logistics%' LIMIT 5"
    )
    
    # Get placements for Northwind
    test_query(
        "Placements for Northwind",
        "SELECT RESOURCE_NAME, POSITION, ACTIVE FROM entity_placement WHERE CUSTOMER_NAME LIKE '%Northwind Logistics%' LIMIT 5"
    )

# Question 3: Customer with most open opportunities
print("\n\nQUESTION 3: Which customer has the most open opportunities?")
test_query(
    "Count opportunities by company",
    """SELECT c.Company_Name, COUNT(*) as opp_count
       FROM entityopportunity o
       LEFT JOIN Entity_Company c ON o.COMPANY_EXD_OBJECT_ID = c.Entity_ID
       WHERE o.STATUS = 'Active'
       GROUP BY c.Company_Name
       ORDER BY opp_count DESC
       LIMIT 10"""
)

# Also check without JOIN to see raw data
print("\n🔍 Checking raw opportunity data...")
test_query(
    "Sample opportunities with company info",
    "SELECT OPPORTUNITY_NAME, COMPANY, COMPANY_EXD_OBJECT_ID, OPPORTUNITY_STAGE, STATUS FROM entityopportunity WHERE STATUS = 'Active' LIMIT 5"
)

print("\n" + "="*60)
print("DEBUG COMPLETE")
print("="*60)
