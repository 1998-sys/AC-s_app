from lxml import etree

xml_path = "xml_model\\26-ODS-95-PRE-015-28PT3507.xml"
xsd_path = "xml_model\\PetrobrasSchemaV3.0.0 (1) (1).xsd"

with open(xsd_path, "rb") as f:
    schema_root = etree.XML(f.read())

schema = etree.XMLSchema(schema_root)
parser = etree.XMLParser(schema=schema)

etree.parse(xml_path, parser)

print("XML válido segundo o XSD Petrobras")