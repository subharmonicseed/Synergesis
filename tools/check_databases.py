from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
user = "neo4j"
password = "blackstar1989"

driver = GraphDatabase.driver(uri, auth=(user, password))
with driver.session() as session:
    result = session.run("SHOW DATABASES")
    print("Available databases:")
    for record in result:
        print(record)
