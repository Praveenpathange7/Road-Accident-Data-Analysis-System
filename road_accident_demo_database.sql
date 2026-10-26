-- Road Accident Analysis demo database for MySQL 8+
-- Real aggregate data: MoRTH / Press Information Bureau, calendar year 2022.
-- Source: https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2042509
-- These are State/UT totals, not individual crash records.
-- Import using MySQL Workbench (open this file and click Execute), or:
-- mysql -u YOUR_USER -p < road_accident_demo_database.sql

CREATE DATABASE IF NOT EXISTS road_accident_demo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE road_accident_demo_db;

CREATE TABLE IF NOT EXISTS locations (
  location_id INT PRIMARY KEY,
  location_name VARCHAR(120) NOT NULL UNIQUE,
  location_type ENUM('COUNTRY','STATE','UT','DISTRICT','CITY') NOT NULL,
  parent_location_id INT NULL,
  CONSTRAINT fk_demo_location_parent FOREIGN KEY (parent_location_id) REFERENCES locations(location_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS data_sources (
  source_id INT PRIMARY KEY,
  publisher VARCHAR(180) NOT NULL,
  title VARCHAR(255) NOT NULL,
  source_url VARCHAR(600) NOT NULL,
  data_year SMALLINT NULL,
  accessed_on DATE NOT NULL,
  notes TEXT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS road_types (
  road_type_id INT PRIMARY KEY,
  road_type_name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS accident_statistics (
  statistic_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  location_id INT NOT NULL,
  source_id INT NOT NULL,
  road_type_id INT NOT NULL,
  statistic_year SMALLINT NOT NULL,
  accidents_reported INT UNSIGNED NULL,
  persons_killed INT UNSIGNED NULL,
  persons_injured INT UNSIGNED NULL,
  UNIQUE KEY uq_demo_stat (location_id, source_id, road_type_id, statistic_year),
  KEY ix_demo_year (statistic_year),
  CONSTRAINT fk_demo_stat_location FOREIGN KEY (location_id) REFERENCES locations(location_id),
  CONSTRAINT fk_demo_stat_source FOREIGN KEY (source_id) REFERENCES data_sources(source_id),
  CONSTRAINT fk_demo_stat_road_type FOREIGN KEY (road_type_id) REFERENCES road_types(road_type_id)
) ENGINE=InnoDB;

-- India (id 1), followed by 28 States and 8 Union Territories.
INSERT IGNORE INTO locations (location_id, location_name, location_type, parent_location_id) VALUES
(1,'India','COUNTRY',NULL),
(2,'Andhra Pradesh','STATE',1),
(3,'Arunachal Pradesh','STATE',1),
(4,'Assam','STATE',1),
(5,'Bihar','STATE',1),
(6,'Chhattisgarh','STATE',1),
(7,'Goa','STATE',1),
(8,'Gujarat','STATE',1),
(9,'Haryana','STATE',1),
(10,'Himachal Pradesh','STATE',1),
(11,'Jharkhand','STATE',1),
(12,'Karnataka','STATE',1),
(13,'Kerala','STATE',1),
(14,'Madhya Pradesh','STATE',1),
(15,'Maharashtra','STATE',1),
(16,'Manipur','STATE',1),
(17,'Meghalaya','STATE',1),
(18,'Mizoram','STATE',1),
(19,'Nagaland','STATE',1),
(20,'Odisha','STATE',1),
(21,'Punjab','STATE',1),
(22,'Rajasthan','STATE',1),
(23,'Sikkim','STATE',1),
(24,'Tamil Nadu','STATE',1),
(25,'Telangana','STATE',1),
(26,'Tripura','STATE',1),
(27,'Uttarakhand','STATE',1),
(28,'Uttar Pradesh','STATE',1),
(29,'West Bengal','STATE',1),
(30,'Andaman and Nicobar Islands','UT',1),
(31,'Chandigarh','UT',1),
(32,'Dadra and Nagar Haveli and Daman and Diu','UT',1),
(33,'Delhi','UT',1),
(34,'Jammu and Kashmir','UT',1),
(35,'Ladakh','UT',1),
(36,'Lakshadweep','UT',1),
(37,'Puducherry','UT',1);

INSERT IGNORE INTO data_sources (source_id,publisher,title,source_url,data_year,accessed_on,notes) VALUES (1,'Ministry of Road Transport and Highways / Press Information Bureau, Government of India','Road Accidents and Safety Measures - State-wise tables for 2018-2022','https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2042509',2022,'2026-10-24','Official State/UT totals for accidents, persons killed and persons injured. The 2022 Dadra and Nagar Haveli figure includes Daman and Diu; combined using the current Union Territory name.');
INSERT IGNORE INTO road_types (road_type_id,road_type_name) VALUES (1,'All road categories'),(2,'National Highway'),(3,'State Highway'),(4,'Other Road');

-- One India total and 36 State/UT totals. Road type 1 means all road categories.
INSERT IGNORE INTO accident_statistics (location_id,source_id,road_type_id,statistic_year,accidents_reported,persons_killed,persons_injured) VALUES
(1,1,1,2022,461312,168491,443366),
(2,1,1,2022,21249,8293,21340),
(3,1,1,2022,227,148,186),
(4,1,1,2022,7023,2994,5637),
(5,1,1,2022,10801,8898,7068),
(6,1,1,2022,13279,5834,11695),
(7,1,1,2022,3011,271,1091),
(8,1,1,2022,15751,7618,15089),
(9,1,1,2022,10429,4915,8519),
(10,1,1,2022,2597,1032,4063),
(11,1,1,2022,5175,3898,3747),
(12,1,1,2022,39762,11702,48154),
(13,1,1,2022,43910,4317,49307),
(14,1,1,2022,54432,13427,55168),
(15,1,1,2022,33383,15224,27239),
(16,1,1,2022,508,127,817),
(17,1,1,2022,246,162,310),
(18,1,1,2022,133,113,107),
(19,1,1,2022,489,73,291),
(20,1,1,2022,11663,5467,10302),
(21,1,1,2022,6138,4756,3324),
(22,1,1,2022,23614,11104,22293),
(23,1,1,2022,211,92,354),
(24,1,1,2022,64105,17884,67703),
(25,1,1,2022,21619,7559,20209),
(26,1,1,2022,575,241,541),
(27,1,1,2022,1674,1042,1613),
(28,1,1,2022,41746,22595,28541),
(29,1,1,2022,13686,6002,12843),
(30,1,1,2022,141,19,136),
(31,1,1,2022,237,83,203),
(32,1,1,2022,196,90,273),
(33,1,1,2022,5652,1461,5201),
(34,1,1,2022,6092,805,8372),
(35,1,1,2022,374,62,346),
(36,1,1,2022,3,2,2),
(37,1,1,2022,1181,181,1282);

-- Example query for dashboard location comparisons (do not include India total in State/UT sums).
SELECT l.location_name, l.location_type, s.statistic_year, s.accidents_reported, s.persons_killed, s.persons_injured FROM accident_statistics AS s JOIN locations AS l ON l.location_id=s.location_id WHERE s.statistic_year=2022 AND s.road_type_id=1 AND l.location_type IN ('STATE','UT') ORDER BY s.accidents_reported DESC;
