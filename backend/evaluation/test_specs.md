# Test Specifications for Course & Grant Mapping

## Course Specifications

### Course 1: Advanced Machine Learning
**Title:** Advanced Machine Learning — Deep Neural Networks & Applications
**Content:**
This is a postgraduate-level course covering advanced topics in machine learning with emphasis on deep neural network architectures, training methodologies, and real-world applications. Students will study convolutional neural networks (CNN) for computer vision tasks including image classification, object detection, and semantic segmentation. The course also covers recurrent neural networks (RNN), long short-term memory networks (LSTM), and attention mechanisms with Transformer architectures for natural language processing tasks such as machine translation, text summarization, and question answering. Practical sessions involve implementing models using PyTorch and TensorFlow on GPU clusters, with a final project requiring students to design, train, and evaluate a deep learning system on a real-world dataset.

### Course 2: Cybersecurity & Network Defense
**Title:** Network Security — Intrusion Detection, Cryptography & Ethical Hacking
**Content:**
This course provides comprehensive coverage of modern cybersecurity principles and practices. Topics include network intrusion detection and prevention systems (IDS/IPS), firewall configuration and management, vulnerability assessment and penetration testing methodologies. Students will learn cryptographic protocols including symmetric encryption (AES), asymmetric encryption (RSA, ECC), hash functions (SHA-256), and their applications in secure communication protocols (TLS/SSL, IPsec). The course includes hands-on labs where students perform ethical hacking exercises using tools such as Wireshark, Metasploit, Nmap, and Burp Suite. Additional topics include malware analysis, digital forensics, security governance frameworks (ISO 27001, NIST), and incident response procedures.

### Course 3: Cloud Computing & Distributed Systems
**Title:** Cloud Infrastructure — Scalable Architectures & Microservices
**Content:**
This course explores the design and implementation of cloud-native applications on modern cloud platforms including AWS, Azure, and Google Cloud Platform. Students will learn containerization technologies (Docker, Kubernetes) for deploying and orchestrating microservices-based architectures. The curriculum covers infrastructure-as-code using Terraform and CloudFormation, CI/CD pipelines with Jenkins and GitHub Actions, and serverless computing with AWS Lambda and Azure Functions. Topics also include distributed data storage (NoSQL databases like MongoDB and Cassandra, distributed file systems like HDFS), message queuing systems (Kafka, RabbitMQ), and monitoring/observability tools (Prometheus, Grafana, ELK Stack). Students will complete a capstone project designing a fault-tolerant, auto-scaling cloud application.

### Course 4: Computer Vision & Image Processing
**Title:** Image Processing — Visual Recognition, 3D Reconstruction & Medical Imaging
**Content:**
This advanced course covers fundamental and state-of-the-art techniques in computer vision and image processing. Core topics include image filtering and enhancement, edge detection, feature extraction (SIFT, SURF, ORB), and image segmentation (watershed, graph cuts, U-Net). The course extensively covers convolutional neural network architectures for visual recognition including ResNet, EfficientNet, YOLO, and Vision Transformers (ViT). Advanced topics include 3D computer vision (structure from motion, SLAM, point cloud processing), generative models for image synthesis (GANs, diffusion models), and medical image analysis (CT/MRI segmentation, disease classification). Practical sessions use OpenCV, scikit-image, and PyTorch.

### Course 5: Natural Language Processing
**Title:** Natural Language Processing — Transformers, LLMs & Multilingual Systems
**Content:**
This course covers modern natural language processing techniques from foundational concepts to cutting-edge large language models. Students will learn text preprocessing, tokenization, word embeddings (Word2Vec, GloVe, FastText), and contextual embeddings (BERT, RoBERTa). The curriculum includes sequence-to-sequence models, attention mechanisms, and the Transformer architecture in depth. Topics span fine-tuning pre-trained language models, prompt engineering, retrieval-augmented generation (RAG), and instruction tuning. The course also covers multilingual NLP challenges including cross-lingual transfer learning, machine translation evaluation metrics, and low-resource language processing. Students will build applications including chatbots, document summarization systems, and sentiment analysis pipelines.

---

## Grant Specifications

### Grant 1: Explainable AI
**Title:** Explainable Artificial Intelligence for Healthcare Decision Support Systems
**Content:**
This research proposes developing interpretable deep learning models for clinical decision support in radiology and pathology. Current AI diagnostic systems achieve high accuracy but operate as black boxes, limiting clinician trust and regulatory approval. We will develop novel explainability methods combining attention visualization, concept-based explanations, and counterfactual reasoning to provide radiologists with transparent rationales for AI-assisted diagnoses. The project will validate these methods on chest X-ray classification (pneumonia, COVID-19, tuberculosis), mammography lesion detection, and histopathology cancer grading. We will conduct clinician-in-the-loop user studies to quantify improvements in diagnostic accuracy and trust. Deliverables include open-source XAI toolkits, annotated benchmark datasets, and peer-reviewed publications.

### Grant 2: IoT Security
**Title:** Lightweight Cryptographic Protocols for Resource-Constrained IoT Devices in Smart Cities
**Content:**
This project addresses the critical security challenges posed by the proliferation of Internet of Things (IoT) devices in smart city deployments. Traditional cryptographic protocols are computationally expensive for battery-powered sensors with limited memory and processing capabilities. We propose developing a framework of lightweight cryptographic primitives optimized for IoT constraints while maintaining robust security guarantees against quantum and classical adversaries. The research will investigate hardware-accelerated implementation of post-quantum cryptographic algorithms (CRYSTALS-Kyber, Dilithium) on ARM Cortex-M microcontrollers, novel key management protocols for mesh networks, and intrusion detection systems tailored for IoT traffic patterns. Real-world validation will be conducted on a smart water metering testbed deployed in collaboration with municipal authorities.

### Grant 3: Federated Learning
**Title:** Privacy-Preserving Federated Learning for Cross-Institutional Medical Research
**Content:**
This research initiative aims to develop federated learning frameworks that enable collaborative training of medical AI models across multiple hospitals without sharing sensitive patient data. Current regulations (HIPAA, GDPR) severely restrict data sharing between institutions, hampering the development of robust diagnostic models that require diverse, multi-center training data. We will design novel federated optimization algorithms that are resilient to heterogeneous data distributions (non-IID data), communication-efficient through gradient compression and asynchronous aggregation, and provably privacy-preserving via differential privacy guarantees. The framework will be validated on multi-institutional cohorts for predicting sepsis onset from ICU time-series data and classifying skin lesions from dermatoscopic images. We will also address the challenge of model fairness across demographic subgroups.

### Grant 4: Sustainable AI
**Title:** Energy-Efficient Training and Deployment of Large Language Models for Southeast Asian Languages
**Content:**
This project addresses the environmental and accessibility challenges of large language models (LLMs) for under-resourced Southeast Asian languages including Malay, Thai, Vietnamese, and Tagalog. Training state-of-the-art LLMs currently requires massive computational resources, resulting in significant carbon footprints and excluding researchers in developing nations. We propose developing parameter-efficient fine-tuning methods (LoRA, QLoRA, adapter-based approaches) combined with knowledge distillation techniques to create compact yet performant models. The research will explore multilingual transfer learning strategies to leverage high-resource language models for improving low-resource language performance. We will create open benchmark datasets for Southeast Asian NLP tasks and deploy optimized inference engines suitable for deployment on edge devices. The project includes a carbon-aware training scheduler that adapts computation to periods of high renewable energy availability.

### Grant 5: Blockchain & Supply Chain
**Title:** Blockchain-Based Traceability Framework for Halal Food Supply Chains in ASEAN
**Content:**
This research proposes a comprehensive blockchain-based traceability system for halal food supply chains spanning multiple ASEAN countries. Current halal certification processes rely on paper-based documentation and centralized databases that are vulnerable to fraud, lack transparency, and create inefficiencies in cross-border trade. We will develop a permissioned blockchain architecture using Hyperledger Fabric that enables immutable recording of halal certification events from farm to fork, integrating IoT sensors for real-time monitoring of cold chain integrity and GPS tracking for logistics verification. The system will incorporate smart contracts for automated halal compliance verification and cross-border regulatory reporting aligned with Malaysian JAKIM, Indonesian MUI, and Singaporean MUIS standards simultaneously. The project includes rigorous testing on beef and poultry supply chains between Malaysia, Indonesia, and Thailand.