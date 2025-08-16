# Architecture Notes

This document outlines some of the key design choices made during the development of the Planetastic connector.

## Choice of `dump1090` Data Stream: SBS-1

The script is designed to consume the **SBS-1 (BaseStation)** format data stream from `dump1090` (typically on port 30003). This choice was made after considering the available alternatives.

### Alternatives Considered

1.  **JSON Format:** Most `dump1090` forks provide a JSON endpoint that contains a periodically updated list of all currently tracked aircraft.
    -   **Pros:** Easy to parse in Python; provides a complete snapshot.
    -   **Cons:** It is a "pull" model. The script would need to poll this endpoint periodically (e.g., every 5-10 seconds). This adds complexity (managing timers, handling request failures) and can introduce latency. It's less ideal for a real-time, event-driven application.

2.  **Beast Binary Format:** This is a more compact, binary format that provides raw Mode S message data.
    -   **Pros:** Very efficient and low-latency. It is the "native" format for many decoders.
    -   **Cons:** Requires a more complex binary parser to decode the messages. While libraries exist for this, it adds a layer of dependency and complexity that is not necessary for our goal of extracting basic position and callsign information.

### Rationale for Choosing SBS-1

The SBS-1 format was chosen as the best compromise for this project's goals:

-   **Simplicity:** It is a simple, line-based, comma-separated text format. This makes it trivial to parse with basic Python string operations, keeping the script lightweight and easy to maintain.
-   **Real-Time Push Model:** `dump1090` pushes data to the connected client as soon as it's available. This event-driven model is a perfect fit for our application, as we can process messages as they arrive without implementing our own polling logic.
-   **Broad Compatibility:** The SBS-1 format is a long-standing, de facto standard supported by nearly all `dump1090` forks and many other ADSB decoders. This ensures the script will work for the widest possible range of user setups.
-   **Sufficient Detail:** While not as detailed as the raw Beast format, the SBS-1 stream contains all the necessary fields (callsign, position, altitude, speed, etc.) to fulfill the requirements of this project.

The main drawback of the SBS-1 format is that data for a single aircraft is fragmented across multiple message types. This was addressed by implementing a stateful in-memory database to aggregate the messages, which provides a robust and reliable way to build a complete picture of each aircraft before broadcasting.
