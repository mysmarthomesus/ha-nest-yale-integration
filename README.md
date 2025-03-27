# ha-nest-yale-integration

**Custom Home Assistant integration for Nest x Yale door locks.**  
This integration enables basic monitoring and limited control of Nest x Yale smart locks within Home Assistant.

---

## 🔧 Features

- Battery level monitoring (in progress)
- Door lock/unlock status reporting  
- Basic door control (in progress)  
- Real-time updates via Nest API (partially implemented)

---

## ⚠️ Experimental Plugin

> ⚠️ **Warning: This integration is experimental and not ready for production use.**

This project is an early-stage prototype attempting to reverse engineer the Nest x Yale lock protocol.  
It is based on the amazing reverse engineering work done in the [Homebridge Nest Plugin](https://github.com/chrisjshull/homebridge-nest).

At present, only **three message types** have been decoded—just enough to show basic lock status and telemetry.  
Most functionality, including full control and feedback, is incomplete or non-functional.

---

## 🚫 Do Not Use In Production

- Do **NOT** install this on your production Home Assistant instance.
- Many core features are still under development or unreliable.
- Expect bugs, incomplete features, and breaking changes.

---

## 🧠 Community Help Needed

This project is open to contributions from the community.  
If you have experience with:

- Home Assistant custom component development
- Reverse engineering APIs and embedded devices
- Protocol Buffers (Protobuf)
- General debugging of smart home integrations

Your input would be incredibly valuable!

You can contribute by:

- Submitting pull requests
- Opening issues with logs or analysis
- Reverse engineering additional messages and formats

---

## 📄 License

This project is licensed under the MIT License.

---

## 🙌 Acknowledgements

- Thanks to [@chrisjshull](https://github.com/chrisjshull) and contributors of the [Homebridge Nest Plugin](https://github.com/chrisjshull/homebridge-nest) for foundational protocol insights.
