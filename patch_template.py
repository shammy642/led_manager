{% if dnsmasq_status %}
    <div class="dnsmasq-status">
        <p>
            <strong>DHCP Status:</strong>
            {% if dnsmasq_status.running %}
                <span style="color: green;">Running</span>
            {% else %}
                <span style="color: red;">Stopped / Error</span>
            {% endif %}
        </p>
        {% if not dnsmasq_status.running and dnsmasq_status.status_text %}
            <pre class="dnsmasq-error">{{ dnsmasq_status.status_text }}</pre>
        {% endif %}
    </div>
{% endif %}
