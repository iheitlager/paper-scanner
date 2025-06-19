import unittest
import sys
from io import StringIO
from paper_scanner.advanced_section_parser import AcademicPaperParser  # Assuming the class is in a file called academic_paper_parser.py
import re

BIG_TEXT = '''"# Academic Paper Analysis\n\n## 1. PAPER_HEADER:\n**1.1. TITLE:** How do collaborative systems affect organizational agility and performance in supply chains?\n\n**1.2. AUTHORS:** Hangju Seo, Heejun Cho, Donghyuk Jo\n\n**1.3. YEAR:** 2025\n\n## 2. SUMMARY:\nThis study examines the impact of collaborative systems (CS) quality on organizational agility and corporate performance within supply chain networks. The research focuses on how different quality dimensions of collaborative systems\u2014system quality, information quality, and service quality\u2014influence information collaboration and operational collaboration among supply chain partners. The authors argue that in the post-COVID era, organizations need enhanced collaborative systems to respond swiftly to environmental uncertainties and maintain competitive advantage.\n\nThe study employs a quantitative approach using structural equation modeling (SEM) to analyze data from 344 South Korean companies with experience in integrated collaboration systems. The findings reveal that information quality is most crucial for information collaboration, while service quality significantly impacts operational collaboration. Both types of collaboration positively affect organizational agility and corporate performance, with operational collaboration showing stronger effects than information collaboration. The research provides valuable insights for organizations seeking to optimize their collaborative systems for improved supply chain performance.\n\n## 3. RESEARCH_QUESTION:\nHow do collaborative systems quality factors affect organizational agility and corporate performance through information collaboration and operational collaboration in supply chain networks?\n\n## 4. METHODOLOGY:\n**4.1. EMPIRICAL_BASE:** Yes, the study has a strong empirical base with survey data collected from 344 South Korean companies from June to October 2023.\n\n**4.2. METHODOLOGY_CLASS:** Quantitative research using Covariance-Based Structural Equation Modeling (CB-SEM) with AMOS 27.0 software.\n\n## 5. VENDORS:\n**5.1. IT_SUPPLIER:** \n- Walmart's Retail Link (collaborative system platform)\n- Boeing's Exostar (collaborative system platform)\n- Procter & Gamble's CPFR system (collaborative planning, forecasting, and replenishment system)\n\n**5.2. REGULAR_SUPPLIER:**\n- No specific regular suppliers mentioned in the study; the focus is on supply chain partners in general rather than specific supplier companies\n\n## 6. INNOVATION_MECHANISMS:\n\n**6.1. CONTEXTS:**\n- Post-COVID pandemic business environment requiring enhanced digital collaboration\n- Rapidly evolving business conditions demanding swift organizational responses\n- Complex global supply chain networks requiring real-time coordination\n- Environmental uncertainty necessitating organizational agility\n- Digital transformation acceleration in supply chain management\n\n**6.2. MECHANISMS:**\n- **Information-Driven Collaboration:** Real-time data sharing and knowledge exchange between supply chain partners to enhance decision-making quality and reduce uncertainties\n- **System-Driven Integration:** Technical platform capabilities enabling seamless coordination and communication across supply chain networks\n- **Service-Driven Support:** User experience optimization through responsive problem-solving and platform convenience to facilitate operational workflows\n- **Collaboration-Driven Agility:** Joint operational processes and synchronized activities enabling rapid response to market changes and customer demands\n- **Quality-Driven Performance:** Comprehensive collaborative system quality encompassing technical, informational, and service dimensions to optimize organizational outcomes\n\n**6.3. OUTCOMES:**\n- **Enhanced Organizational Agility:** Improved ability to respond quickly to customer demands, launch new products rapidly, adjust production volumes, and handle operational problems\n- **Improved Corporate Performance:** Better product quality, on-time delivery performance, accurate quantity fulfillment, and higher partner satisfaction\n- **Operational Efficiency:** Reduced production and transportation times, cost savings, and enhanced competitiveness\n- **Supply Chain Resilience:** Better coordination among partners, reduced disruptions, and improved risk management capabilities\n- **Competitive Advantage:** Sustained market position through superior collaborative capabilities and responsive operations"'''


class TestAcademicPaperParser(unittest.TestCase):
    def setUp(self):
        self.parser = AcademicPaperParser()
        self.maxDiff = None  # Show full diff if assertion fails
        
        # Capture stderr to avoid printing during tests
        self.stderr_backup = sys.stderr
        sys.stderr = StringIO()
        
    def tearDown(self):
        # Restore stderr
        sys.stderr = self.stderr_backup
        
    def test_parse_sections(self):
        # Parse the input
        parsed_sections = self.parser.parse_sections(BIG_TEXT)
        self.assertEqual(len(parsed_sections), 6)
        self.assertIn("PAPER_HEADER", parsed_sections)
        self.assertIn("SUMMARY", parsed_sections)
        self.assertIn("RESEARCH_QUESTION", parsed_sections)
        self.assertIn("METHODOLOGY", parsed_sections)
        self.assertIn("VENDORS", parsed_sections)
        self.assertIn("INNOVATION_MECHANISMS", parsed_sections)
       
    def test_extract_paper_header(self):
        _INPUT= '1.1. **TITLE:** How do collaborative systems affect organizational agility and performance in supply chains?\n\n1.2. **AUTHORS:** Hangju Seo, Heejun Cho, Donghyuk Jo\n\n1.3. **YEAR:** 2025\n\n'

        result = self.parser.extract_paper_header(_INPUT)
        self.assertEqual(result["YEAR"], "2025")
        self.assertEqual(result["TITLE"], "How do collaborative systems affect organizational agility and performance in supply chains?")
        self.assertIn(result["AUTHORS"], "Hangju Seo, Heejun Cho, Donghyuk Jo")

    def test_innovation_mechanisms(self):
        # Parse the input
        parsed_sections = self.parser.parse_sections(BIG_TEXT)
        self.assertIn("INNOVATION_MECHANISMS", parsed_sections)
        cmo = self.parser.parse_innovation_mechanisms(parsed_sections['INNOVATION_MECHANISMS'])
        self.assertEqual(len(cmo), 3)
        self.assertEqual(len(cmo['CONTEXTS']), 5)
        self.assertEqual(len(cmo['MECHANISMS']), 5)
        self.assertEqual(len(cmo['OUTCOMES']), 5)

    def test_vendors(self):
        # Parse the input
        parsed_sections = self.parser.parse_sections(BIG_TEXT)
        self.assertIn("VENDORS", parsed_sections)
        vendor = self.parser.parse_vendors(parsed_sections['VENDORS'])
        self.assertEqual(len(vendor), 2)
        self.assertEqual(len(vendor['IT_SUPPLIER']), 3)
        self.assertEqual(len(vendor['REGULAR_SUPPLIER']), 1)


    # def test_parse_mechanisms1(self):
    #     INPUT = """1. Cooperation-Driven Integration: Strategic alliances with technology partners to leverage external capabilities while mitigating transformation costs\n2. Platform-Driven Innovation: Establishing digital ecosystems that connect multiple stakeholders through standardized interfaces to foster new service development\n3. Outsourcing-Driven Efficiency: Leveraging external IT service providers to manage non-core technology functions while focusing on customer-facing activities\n4. API-Driven Connectivity: Implementing standardized interfaces that allow for seamless integration of third-party services into existing business processes\n5. Ecosystem-Driven Growth: Building networks with technology companies to enhance product portfolios and access innovative business models\n6. Infrastructure-Sharing-Driven Cost Reduction: Collaborating with industry partners on technological foundations to reduce individual transformation investments"""

    #     items = self.parser.parse_steps(INPUT)

    #     self.assertEqual(len(items), 6)


    # def test_process_paper_analysis(self):
    #     # Parse the input
    #     result = self.parser.process_paper_analysis(BIG_TEXT)
    #     self.assertEqual(len(result), 6)
    #     self.assertIn("PAPER_HEADER", result)
    #     self.assertIn("SUMMARY", result)
    #     self.assertIn("RESEARCH_QUESTION", result)
    #     self.assertIn("METHODOLOGY", result)
    #     self.assertIn("VENDORS", result)
    #     self.assertIn("INNOVATION_MECHANISMS", result)

    # def test_single_line(self):
    #     INPUT1 = """## TITLE_AUTHORS
    #     Integrating digital transformation"""

    #     EXPECTED_OUTPUT = 'Integrating digital transformation'
        
    #     # Parse the input
    #     parsed_sections = self.parser.parse_sections(INPUT1)
    #     # Check if TITLE_AUTHORS section exists and matches expected output
    #     self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
    #     self.assertEqual(parsed_sections["TITLE_AUTHORS"], EXPECTED_OUTPUT, 
    #                      "TITLE_AUTHORS content does not match expected output")

    # def test_single_line_item(self):
    #     INPUT1 = """## 1. TITLE_AUTHORS
    #     Integrating digital transformation"""

    #     EXPECTED_OUTPUT = 'Integrating digital transformation'
        
    #     # Parse the input
    #     parsed_sections = self.parser.parse_sections(INPUT1)
    #     # Check if TITLE_AUTHORS section exists and matches expected output
    #     self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
    #     self.assertEqual(parsed_sections["TITLE_AUTHORS"], EXPECTED_OUTPUT, 
    #                      "TITLE_AUTHORS content does not match expected output")

    # def test_section_header_skipped(self):
    #     INPUT1 = """# Academic Paper Analysis\n\n## 1. TITLE_AUTHORS
    #     Integrating digital transformation"""

    #     EXPECTED_OUTPUT = 'Integrating digital transformation'
        
    #     # Parse the input
    #     parsed_sections = self.parser.parse_sections(INPUT1)
    #     # Check if TITLE_AUTHORS section exists and matches expected output
    #     self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
    #     self.assertEqual(len(parsed_sections), 1,  
    #                      "Header not skipped")

    # def test_multi_line_item(self):
    #     INPUT = """# Academic Paper Analysis\n\n## 1. TITLE_AUTHORS\nIntegrating digital transformation\n## 2. ABSTRACT_SUMMARY\nThis study explores how digital"""

    #     EXPECTED_OUTPUT1 = 'Integrating digital transformation'
    #     EXPECTED_OUTPUT2 = 'This study explores how digital'

    #     # Parse the input
    #     parsed_sections = self.parser.parse_sections(INPUT)
    #     # Check if TITLE_AUTHORS section exists and matches expected output
    #     self.assertIn("TITLE_AUTHORS", parsed_sections, "TITLE_AUTHORS section not found in parsed result")
    #     self.assertEqual(parsed_sections["TITLE_AUTHORS"], EXPECTED_OUTPUT1, 
    #                      "TITLE_AUTHORS content does not match expected output")
    #     self.assertIn("ABSTRACT_SUMMARY", parsed_sections, "ABSTRACT_SUMMARY section not found in parsed result")
    #     self.assertEqual(parsed_sections["ABSTRACT_SUMMARY"], EXPECTED_OUTPUT2, 
    #                      "ABSTRACT_SUMMARY content does not match expected output")
        
    # def test_parse_mechanisms1(self):
    #     INPUT = """1. Cooperation-Driven Integration: Strategic alliances with technology partners to leverage external capabilities while mitigating transformation costs\n2. Platform-Driven Innovation: Establishing digital ecosystems that connect multiple stakeholders through standardized interfaces to foster new service development\n3. Outsourcing-Driven Efficiency: Leveraging external IT service providers to manage non-core technology functions while focusing on customer-facing activities\n4. API-Driven Connectivity: Implementing standardized interfaces that allow for seamless integration of third-party services into existing business processes\n5. Ecosystem-Driven Growth: Building networks with technology companies to enhance product portfolios and access innovative business models\n6. Infrastructure-Sharing-Driven Cost Reduction: Collaborating with industry partners on technological foundations to reduce individual transformation investments"""

    #     items = self.parser.parse_steps(INPUT)

    #     self.assertEqual(len(items), 6)


    # def test_parse_mechanisms2(self):
    #     INPUT = """[Coordination]-Driven [Alignment]: Integration of processes, systems, and workflows between partners to ensure synchronized operations and strategic coherence\n\n[Communication]-Driven [Transparency]: Real-time data sharing and open exchange of information enabling visibility across the supply chain\n\n[Relationship]-Driven [Trust]: Cultivating strong inter-organizational bonds to facilitate risk sharing and collaborative problem-solving\n\n[Technology]-Driven [Integration]: Implementing shared digital platforms to connect disparate systems and enable seamless information flow\n\n[Data]-Driven [Decision-making]: Leveraging analytics and shared datasets to make informed strategic choices based on real-time insights\n\n[Talent]-Driven [Innovation]: Recruiting digital specialists to drive transformation initiatives and foster a culture of technological advancement\n\n[Leadership]-Driven [Vision]: Executive commitment to digital initiatives that aligns transformation efforts with strategic goals\n\n[Culture]-Driven [Adaptation]: Fostering an environment where digital thinking becomes the norm, enabling continuous innovation and responsiveness"""

    #     items = self.parser.parse_steps(INPUT)

    #     self.assertEqual(len(items), 8)
    #     self.assertIn("[Coordination]-Driven [Alignment]", items[0], "Content missing")


    # def test_parser(self):
    #     # INPUT = """# Academic Paper Analysis\n\n## 1. TITLE_AUTHORS\n\"Decoding digital transformational outsourcing: The role of service providers' capabilities\" by Sudipto Mazumder and Swapnil Garg (2021)\n\n## 2. ABSTRACT_SUMMARY\nThe paper examines how the business process outsourcing (BPO) industry has been disrupted by two major shifts: the significant transfer of value creation activities from clients to service providers, and pervasive digital penetration, resulting in Digital Transformational Outsourcing (DTO). The authors study 26 global BPO providers to identify six dynamic capabilities essential for service providers in this new context and use fuzzy-set Qualitative Comparative Analysis to identify configurations for high and low performance.\n\n## 3. RESEARCH_QUESTION\nWhat configurations of dynamic capabilities (i.e., consultative, orchestration, standardization, network building and management, knowledge access, and generation/sharing of actionable insights) enable outsourcing service provider (OSP) performance in the Digital Transformational Outsourcing context?\n\n## 4. METHODOLOGY\nThe study used a mixed-methods approach combining:\n1. Literature review of outsourcing, service innovation, and digital transformation literature\n2. Semi-structured interviews with 18 industry experts from global outsourcing firms\n3. Firm-level secondary data collection from multiple sources (analyst reports, databases, annual reports, press releases)\n4. Necessary Condition Analysis (NCA) to identify necessary capabilities\n5. Fuzzy-set Qualitative Comparative Analysis (fsQCA) to identify sufficient configurations of capabilities leading to high/low performance\n\n## 5. KEY_FINDINGS\n1. Two capabilities (knowledge access and insights generation/sharing) are necessary conditions for high OSP performance in the DTO context.\n2. High performance capability configurations vary by firm scope (broad vs. narrow):\n   - Broad scope firms succeed with \"orchestration recipes\" focusing on orchestration capability, consultative capability, and minimal standardization\n   - Narrow scope firms succeed with \"hyper-standardizing recipes\" emphasizing standardization capability\n3. Low performance occurs when firms lack implementation abilities (for broad scope firms) or when narrow scope firms possess \"unaware\" or \"reluctant\" capability configurations.\n4. Dynamic capabilities work in configurational patterns rather than in isolation, showing equifinality (multiple paths to success) and asymmetry (paths to low performance are not simply the inverse of paths to high performance).\n5. The findings demonstrate the contextual embeddedness of dynamic capabilities in the DTO environment.\n\n## 6. LIMITATIONS\n1. Sample size was limited to 26 firms due to industry fragmentation and information availability\n2. The identified capabilities may not be exhaustive, and additional capabilities may emerge in the rapidly changing DTO context\n3. The cross-sectional nature of the study limits insights into how capability configurations change over time\n4. Limited methods for predictive validity analysis in small-N QCA samples\n5. Focused on BPO industry only, though ITO (IT Outsourcing) is converging with BPO\n\n## 7. FUTURE_WORK\n1. Explore how capability configurations change over time through longitudinal investigations\n2. Extend the research to include IT outsourcing (ITO) as BPO and ITO industries converge\n3. Identify additional emerging capabilities as the DTO context evolves\n4. Develop methods for predictive validity analysis in small-N QCA samples\n5. Investigate alternative units of analysis beyond the firm level to explore OSP capabilities\n\n## 8. CITATIONS\nKey cited papers include:\n- Teece (2007) on dynamic capabilities framework\n- Lacity et al. (2016) on business process outsourcing\n- Vial (2019) on digital transformation\n- Warner & Wäger (2019) on dynamic capabilities for digital transformation\n- Verhoef et al. (2021) on digital transformation\n- Mikalef & Pateli (2017) on IT-enabled dynamic capabilities\n- Ragin (2007) on fuzzy-set Qualitative Comparative Analysis\n\n## 9. IT_SUPPLIER: Yes\nThe article specifically focuses on IT Service Providers as external resources, referring to them as Outsourcing Service Providers (OSPs) in the Digital Transformational Outsourcing (DTO) context. The entire paper examines how these external providers develop and utilize capabilities to create value for their client firms.\n\n## 10. VENDORS\nThe paper examines 26 global business process outsourcing providers, including:\n- Human Resources Outsourcing (HRO) specialists\n- Customer Care service providers\n- Multi-service providers offering finance, accounting, human resources, and other services\n- Broad scope providers offering end-to-end services\n- Narrow scope providers focusing on specific service domains\n\n## 11. MECHANISMS\n1. Consultative-Driven Engagement: Identifying client's stated and unstated needs using orthodox and empathy-driven approaches to conceptualize innovative digital offerings\n2. Orchestration-Driven Integration: Seamlessly combining digital and non-digital resources while addressing information security and compliance concerns\n3. Standardization-Driven Efficiency: Implementing reusable and replicable digital solutions across multiple client scenarios with minimal adaptations\n4. Network-Driven Collaboration: Identifying, establishing and managing digital partnerships to expand capability offerings\n5. Knowledge Access-Driven Innovation: Leveraging broad pools of digital knowledge components with limited absorption to enable service transformation\n6. Insights-Driven Value Creation: Generating and sharing actionable intelligence from operational data using advanced analytics to build strategic responses"""
    #     INPUT = """## 9. IT_SUPPLIER\nYes. The article specifically focuses on IT Service Providers as external .\n\n"""
    #     parsed_sections = self.parser.parse_sections(INPUT)
    #     self.assertIn("IT_SUPPLIER", parsed_sections, "IT_SUPPLIER not found")

if __name__ == "__main__":
    unittest.main()