
/**
 * Unit tests for frontend/public/js/app.js
 */

// Mock fetch API
global.fetch = jest.fn();

// Mock Bootstrap Modal
global.bootstrap = {
    Modal: jest.fn().mockImplementation(() => ({
        show: jest.fn(),
        hide: jest.fn(),
    })),
};
bootstrap.Modal.getInstance = jest.fn().mockImplementation(() => ({
    hide: jest.fn(),
}));

// Helper to reset DOM before each test
beforeEach(() => {
    document.body.innerHTML = `
        <div class="container"></div>
        <form id="installation-form"></form>
        <input type="radio" name="mode" value="all_in_one" checked>
        <input type="radio" name="mode" value="ha_secure">
        <div id="ha-config" class="d-none"></div>
        <div id="nodes-config"></div>
        <div id="progress-modal"></div>
        <div id="result-modal"></div>
        <div id="installation-id"></div>
        <div id="current-step"></div>
        <div id="installation-duration"></div>
        <div id="log-content"></div>
        <div id="cancel-btn"></div>
        <div id="close-btn"></div>
        <div id="progress-bar"></div>
        <div id="progress-percentage"></div>
        <div id="progress-text"></div>
        <div id="total-installations"></div>
        <div id="running-installations"></div>
        <div id="successful-installations"></div>
        <div id="failed-installations"></div>
        <table id="installations-table-body"></table>
        <button onclick="addNodeConfig()"></button>
        <button onclick="removeNodeConfig()"></button>
        <button onclick="cancelInstallation()"></button>
        <button onclick="downloadKubeconfig()"></button>
        <button onclick="viewInstallationDetails()"></button>
        <button onclick="cancelInstallationById()"></button>
        <button onclick="deleteInstallation()"></button>
    `;
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Load app.js into the JSDOM environment
    require('./app.js');
});

afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
});

describe('initializeApp', () => {
    test('should call initial data loading and setup functions', () => {
        const loadStatsSpy = jest.spyOn(window, 'loadStats').mockImplementation(() => {});
        const loadInstallationsSpy = jest.spyOn(window, 'loadInstallations').mockImplementation(() => {});
        const setupFormHandlersSpy = jest.spyOn(window, 'setupFormHandlers').mockImplementation(() => {});
        const setupModeSwitchSpy = jest.spyOn(window, 'setupModeSwitch').mockImplementation(() => {});

        window.initializeApp();

        expect(loadStatsSpy).toHaveBeenCalled();
        expect(loadInstallationsSpy).toHaveBeenCalled();
        expect(setupFormHandlersSpy).toHaveBeenCalled();
        expect(setupModeSwitchSpy).toHaveBeenCalled();

        // Check setInterval calls
        expect(setInterval).toHaveBeenCalledTimes(2);
        expect(setInterval).toHaveBeenCalledWith(loadStatsSpy, 30000);
        expect(setInterval).toHaveBeenCalledWith(loadInstallationsSpy, 15000);
    });
});

describe('setupFormHandlers', () => {
    test('should add submit event listener to form', () => {
        const form = document.getElementById('installation-form');
        const addEventListenerSpy = jest.spyOn(form, 'addEventListener');

        window.setupFormHandlers();

        expect(addEventListenerSpy).toHaveBeenCalledWith('submit', expect.any(Function));
    });
});

describe('setupModeSwitch', () => {
    test('should add change event listeners to mode radios', () => {
        const modeRadios = document.querySelectorAll('input[name="mode"]');
        const addEventListenerSpy = jest.spyOn(modeRadios[0], 'addEventListener');

        window.setupModeSwitch();

        expect(addEventListenerSpy).toHaveBeenCalledWith('change', expect.any(Function));
        expect(addEventListenerSpy).toHaveBeenCalledTimes(modeRadios.length);
    });
});

describe('handleModeChange', () => {
    test('should show HA config and add default nodes when switching to ha_secure', () => {
        const haConfig = document.getElementById('ha-config');
        const nodesConfig = document.getElementById('nodes-config');
        const addNodeConfigSpy = jest.spyOn(window, 'addNodeConfig').mockImplementation(() => {});

        // Simulate initial state where no nodes are present
        nodesConfig.innerHTML = '';

        const event = { target: { value: 'ha_secure' } };
        window.handleModeChange(event);

        expect(haConfig.classList.contains('d-none')).toBe(false);
        expect(addNodeConfigSpy).toHaveBeenCalledTimes(4); // 4 default nodes
    });

    test('should hide HA config when switching away from ha_secure', () => {
        const haConfig = document.getElementById('ha-config');
        haConfig.classList.remove('d-none'); // Ensure it's visible initially

        const event = { target: { value: 'all_in_one' } };
        window.handleModeChange(event);

        expect(haConfig.classList.contains('d-none')).toBe(true);
    });
});

describe('handleFormSubmit', () => {
    let showAlertSpy;

    beforeEach(() => {
        showAlertSpy = jest.spyOn(window, 'showAlert').mockImplementation(() => {});
        // Mock fetch for validation
        fetch.mockResponseOnce(JSON.stringify({ valid: true }), { status: 200 });
        // Mock fetch for start
        fetch.mockResponseOnce(JSON.stringify({ success: true, installation_id: 'test-id' }), { status: 202 });

        // Mock DOM elements for form data
        document.getElementById('installation-form').innerHTML = `
            <input name="mode" value="all_in_one">
            <input name="k8s_version" value="1.28.0">
            <input name="cni_provider" value="cilium">
            <input name="pod_cidr" value="10.244.0.0/16">
            <input name="service_cidr" value="10.96.0.0/12">
            <input name="enable_rbac" type="checkbox" checked>
            <input name="enable_network_policies" type="checkbox" checked>
            <input name="enable_monitoring" type="checkbox" checked>
        `;
    });

    test('should handle successful form submission', async () => {
        const showProgressModalSpy = jest.spyOn(window, 'showProgressModal').mockImplementation(() => {});
        const startProgressTrackingSpy = jest.spyOn(window, 'startProgressTracking').mockImplementation(() => {});

        const form = document.getElementById('installation-form');
        await window.handleFormSubmit({ preventDefault: () => {}, target: form });

        expect(fetch).toHaveBeenCalledTimes(2);
        expect(fetch).toHaveBeenCalledWith(
            '/api/v1/installation/validate',
            expect.objectContaining({ method: 'POST' })
        );
        expect(fetch).toHaveBeenCalledWith(
            '/api/v1/installation/start',
            expect.objectContaining({ method: 'POST' })
        );
        expect(showProgressModalSpy).toHaveBeenCalled();
        expect(startProgressTrackingSpy).toHaveBeenCalled();
        expect(showAlertSpy).not.toHaveBeenCalled();
    });

    test('should show alert on validation failure', async () => {
        fetch.mockReset(); // Clear previous mocks
        fetch.mockResponseOnce(JSON.stringify({ valid: false, error: 'Invalid config' }), { status: 200 });

        const form = document.getElementById('installation-form');
        await window.handleFormSubmit({ preventDefault: () => {}, target: form });

        expect(fetch).toHaveBeenCalledTimes(1);
        expect(showAlertSpy).toHaveBeenCalledWith('Configuration validation failed: Invalid config', 'danger');
    });

    test('should show alert on installation start failure', async () => {
        fetch.mockReset(); // Clear previous mocks
        fetch.mockResponseOnce(JSON.stringify({ valid: true }), { status: 200 }); // Validation success
        fetch.mockResponseOnce(JSON.stringify({ success: false, error: 'Server error' }), { status: 500 }); // Start failure

        const form = document.getElementById('installation-form');
        await window.handleFormSubmit({ preventDefault: () => {}, target: form });

        expect(fetch).toHaveBeenCalledTimes(2);
        expect(showAlertSpy).toHaveBeenCalledWith('Installation failed to start: Server error', 'danger');
    });

    test('should show alert on HA mode node count validation failure', async () => {
        fetch.mockReset(); // Clear previous mocks
        showAlertSpy.mockClear();

        document.getElementById('installation-form').innerHTML = `
            <input name="mode" value="ha_secure">
            <input name="k8s_version" value="1.28.0">
        `;
        document.getElementById('nodes-config').innerHTML = `
            <div class="card"></div>
            <div class="card"></div>
            <div class="card"></div>
        `; // Only 3 nodes

        const form = document.getElementById('installation-form');
        await window.handleFormSubmit({ preventDefault: () => {}, target: form });

        expect(showAlertSpy).toHaveBeenCalledWith('HA mode requires at least 4 nodes (1 load balancer + 3 masters)', 'danger');
        expect(fetch).not.toHaveBeenCalled(); // Should not call fetch if client-side validation fails
    });
});

describe('updateProgress', () => {
    test('should update progress bar and text', () => {
        const progressBar = document.getElementById('progress-bar');
        const progressPercentage = document.getElementById('progress-percentage');
        const currentStep = document.getElementById('current-step');
        const installationDuration = document.getElementById('installation-duration');
        const progressText = document.getElementById('progress-text');

        const status = {
            progress_percentage: 50,
            current_step: 5,
            total_steps: 10,
            duration: 123.45,
            status: 'installing'
        };

        window.updateProgress(status);

        expect(progressBar.style.width).toBe('50%');
        expect(progressBar.getAttribute('aria-valuenow')).toBe('50');
        expect(progressPercentage.textContent).toBe('50%');
        expect(currentStep.textContent).toBe('5/10');
        expect(installationDuration.textContent).toBe('2m 3s'); // 123.45 seconds
        expect(progressText.textContent).toBe('Installing Kubernetes...');
    });

    test('should handle pending status', () => {
        const progressText = document.getElementById('progress-text');
        window.updateProgress({ status: 'pending' });
        expect(progressText.textContent).toBe('Preparing installation...');
    });
});

describe('updateLogs', () => {
    test('should update log content and scroll to bottom', () => {
        const logContent = document.getElementById('log-content');
        const logContainer = document.getElementById('log-container');
        logContainer.scrollHeight = 100; // Simulate scrollable content

        const logs = [
            { timestamp: 1678886400, level: 'INFO', message: 'Log message 1' },
            { timestamp: 1678886401, level: 'ERROR', message: 'Log message 2' }
        ];

        window.updateLogs(logs);

        expect(logContent.innerHTML).toContain('Log message 1');
        expect(logContent.innerHTML).toContain('Log message 2');
        expect(logContent.innerHTML).toContain('text-primary'); // INFO color
        expect(logContent.innerHTML).toContain('text-danger'); // ERROR color
        expect(logContainer.scrollTop).toBe(logContainer.scrollHeight); // Auto-scroll
    });
});

describe('handleInstallationComplete', () => {
    test('should hide cancel button, show close button, and show result modal', () => {
        const cancelBtn = document.getElementById('cancel-btn');
        const closeBtn = document.getElementById('close-btn');
        const showResultModalSpy = jest.spyOn(window, 'showResultModal').mockImplementation(() => {});

        cancelBtn.classList.remove('d-none'); // Ensure visible initially
        closeBtn.classList.add('d-none'); // Ensure hidden initially

        window.handleInstallationComplete({ success: true });

        expect(cancelBtn.classList.contains('d-none')).toBe(true);
        expect(closeBtn.classList.contains('d-none')).toBe(false);
        expect(showResultModalSpy).toHaveBeenCalledWith({ success: true });
        expect(setTimeout).toHaveBeenCalled();
    });
});

describe('showResultModal', () => {
    let loadInstallationsSpy;

    beforeEach(() => {
        loadInstallationsSpy = jest.spyOn(window, 'loadInstallations').mockImplementation(() => {});
        jest.spyOn(window, 'downloadKubeconfig').mockImplementation(() => {});
    });

    test('should display success message and details', () => {
        const status = { success: true, duration: 300, installation_id: 'test-id', mode: 'all_in_one' };
        window.showResultModal(status);

        const header = document.getElementById('result-header');
        const title = document.getElementById('result-title');
        const content = document.getElementById('result-content');
        const downloadBtn = document.getElementById('download-kubeconfig');

        expect(header.classList.contains('bg-success')).toBe(true);
        expect(title.innerHTML).toContain('Installation Successful!');
        expect(content.innerHTML).toContain('Kubernetes cluster installed successfully!');
        expect(downloadBtn.classList.contains('d-none')).toBe(false);
        expect(loadInstallationsSpy).toHaveBeenCalled();
    });

    test('should display failure message and troubleshooting', () => {
        const status = { success: false, error_message: 'Some error' };
        window.showResultModal(status);

        const header = document.getElementById('result-header');
        const title = document.getElementById('result-title');
        const content = document.getElementById('result-content');
        const downloadBtn = document.getElementById('download-kubeconfig');

        expect(header.classList.contains('bg-danger')).toBe(true);
        expect(title.innerHTML).toContain('Installation Failed');
        expect(content.innerHTML).toContain('The installation encountered an error');
        expect(content.innerHTML).toContain('Error: Some error');
        expect(downloadBtn.classList.contains('d-none')).toBe(true);
        expect(loadInstallationsSpy).toHaveBeenCalled();
    });
});

describe('cancelInstallation', () => {
    let showAlertSpy;

    beforeEach(() => {
        showAlertSpy = jest.spyOn(window, 'showAlert').mockImplementation(() => {});
        window.currentInstallationId = 'test-id';
        window.progressInterval = setInterval(() => {}, 1000); // Simulate active interval
        fetch.mockResponseOnce(JSON.stringify({ success: true }), { status: 200 });
    });

    test('should cancel installation successfully', async () => {
        await window.cancelInstallation();

        expect(fetch).toHaveBeenCalledWith(
            '/api/v1/installation/test-id/cancel',
            expect.objectContaining({ method: 'POST' })
        );
        expect(showAlertSpy).toHaveBeenCalledWith('Installation cancelled', 'warning');
        expect(clearInterval).toHaveBeenCalledWith(window.progressInterval);
        expect(window.currentInstallationId).toBeNull();
        expect(window.loadInstallations).toHaveBeenCalled();
    });

    test('should show alert on cancellation failure', async () => {
        fetch.mockReset();
        fetch.mockResponseOnce(JSON.stringify({ success: false, error: 'Cancel error' }), { status: 500 });

        await window.cancelInstallation();

        expect(showAlertSpy).toHaveBeenCalledWith('Failed to cancel installation: Cancel error', 'danger');
    });
});

describe('downloadKubeconfig', () => {
    let showAlertSpy;

    beforeEach(() => {
        showAlertSpy = jest.spyOn(window, 'showAlert').mockImplementation(() => {});
        fetch.mockResponseOnce(new Blob(['kubeconfig content']), { status: 200 });
    });

    test('should download kubeconfig successfully', async () => {
        const createElementSpy = jest.spyOn(document, 'createElement');
        const appendChildSpy = jest.spyOn(document.body, 'appendChild');
        const removeChildSpy = jest.spyOn(document.body, 'removeChild');

        await window.downloadKubeconfig('test-id');

        expect(fetch).toHaveBeenCalledWith('/api/v1/installation/test-id/kubeconfig');
        expect(createElementSpy).toHaveBeenCalledWith('a');
        expect(appendChildSpy).toHaveBeenCalled();
        expect(removeChildSpy).toHaveBeenCalled();
        expect(showAlertSpy).not.toHaveBeenCalled();
    });

    test('should show alert on download failure', async () => {
        fetch.mockReset();
        fetch.mockResponseOnce(JSON.stringify({ success: false, error: 'Download error' }), { status: 500 });

        await window.downloadKubeconfig('test-id');

        expect(showAlertSpy).toHaveBeenCalledWith('Failed to download kubeconfig: Download error', 'danger');
    });
});

describe('loadStats', () => {
    let updateStatsSpy;

    beforeEach(() => {
        updateStatsSpy = jest.spyOn(window, 'updateStats').mockImplementation(() => {});
        fetch.mockResponseOnce(JSON.stringify({ total_installations: 5 }), { status: 200 });
    });

    test('should load stats successfully', async () => {
        await window.loadStats();

        expect(fetch).toHaveBeenCalledWith('/api/v1/installation/stats');
        expect(updateStatsSpy).toHaveBeenCalledWith({ total_installations: 5 });
    });

    test('should log error on fetch failure', async () => {
        const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        fetch.mockReset();
        fetch.mockReject(new Error('Network error'));

        await window.loadStats();

        expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load stats:', expect.any(Error));
    });
});

describe('updateStats', () => {
    test('should update stat elements correctly', () => {
        const total = document.getElementById('total-installations');
        const running = document.getElementById('running-installations');
        const successful = document.getElementById('successful-installations');
        const failed = document.getElementById('failed-installations');

        const stats = {
            total_installations: 10,
            status_breakdown: { installing: 2, pending: 1, success: 5, failed: 2 },
            completed_installations: { total_completed: 7, successful: 5, failed: 2 }
        };

        window.updateStats(stats);

        expect(total.textContent).toBe('10');
        expect(running.textContent).toBe('3'); // 2 installing + 1 pending
        expect(successful.textContent).toBe('5');
        expect(failed.textContent).toBe('2');
    });
});

describe('loadInstallations', () => {
    let updateInstallationsTableSpy;

    beforeEach(() => {
        updateInstallationsTableSpy = jest.spyOn(window, 'updateInstallationsTable').mockImplementation(() => {});
        fetch.mockResponseOnce(JSON.stringify({ installations: [{ id: '1' }] }), { status: 200 });
    });

    test('should load installations successfully', async () => {
        await window.loadInstallations();

        expect(fetch).toHaveBeenCalledWith('/api/v1/installation/list');
        expect(updateInstallationsTableSpy).toHaveBeenCalledWith([{ id: '1' }]);
    });

    test('should log error on fetch failure', async () => {
        const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        fetch.mockReset();
        fetch.mockReject(new Error('Network error'));

        await window.loadInstallations();

        expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load installations:', expect.any(Error));
    });
});

describe('updateInstallationsTable', () => {
    test('should display no installations message when empty', () => {
        const tbody = document.getElementById('installations-table-body');
        window.updateInstallationsTable([]);
        expect(tbody.innerHTML).toContain('No installations found');
    });

    test('should display installations correctly', () => {
        const tbody = document.getElementById('installations-table-body');
        const installations = [
            {
                installation_id: 'id1',
                mode: 'all_in_one',
                status: 'installing',
                progress_percentage: 50,
                duration: 120,
                completed: false,
                success: null
            },
            {
                installation_id: 'id2',
                mode: 'ha_secure',
                status: 'success',
                progress_percentage: 100,
                duration: 300,
                completed: true,
                success: true
            }
        ];
        window.updateInstallationsTable(installations);

        expect(tbody.innerHTML).toContain('id1');
        expect(tbody.innerHTML).toContain('all-in-one');
        expect(tbody.innerHTML).toContain('installing');
        expect(tbody.innerHTML).toContain('50%');
        expect(tbody.innerHTML).toContain('2m 0s');

        expect(tbody.innerHTML).toContain('id2');
        expect(tbody.innerHTML).toContain('ha-secure');
        expect(tbody.innerHTML).toContain('success');
        expect(tbody.innerHTML).toContain('100%');
        expect(tbody.innerHTML).toContain('5m 0s');
    });
});

describe('formatDuration', () => {
    test('should format seconds correctly', () => {
        expect(window.formatDuration(30)).toBe('30s');
        expect(window.formatDuration(123)).toBe('2m 3s');
        expect(window.formatDuration(3600)).toBe('1h 0m');
        expect(window.formatDuration(3723)).toBe('1h 2m');
    });
});

describe('showAlert', () => {
    test('should add and remove alert div', () => {
        window.showAlert('Test message', 'success');
        const alertDiv = document.querySelector('.alert');
        expect(alertDiv).not.toBeNull();
        expect(alertDiv.textContent).toContain('Test message');
        expect(alertDiv.classList.contains('alert-success')).toBe(true);

        jest.advanceTimersByTime(5000);
        expect(document.querySelector('.alert')).toBeNull();
    });
});

describe('cancelInstallationById', () => {
    let showAlertSpy;

    beforeEach(() => {
        showAlertSpy = jest.spyOn(window, 'showAlert').mockImplementation(() => {});
        jest.spyOn(window, 'loadInstallations').mockImplementation(() => {});
        window.confirm = jest.fn(() => true); // Mock confirm to return true
        fetch.mockResponseOnce(JSON.stringify({ success: true }), { status: 200 });
    });

    test('should cancel installation by ID successfully', async () => {
        await window.cancelInstallationById('test-id');

        expect(window.confirm).toHaveBeenCalled();
        expect(fetch).toHaveBeenCalledWith(
            '/api/v1/installation/test-id/cancel',
            expect.objectContaining({ method: 'POST' })
        );
        expect(showAlertSpy).toHaveBeenCalledWith('Installation cancelled', 'warning');
        expect(clearInterval).toHaveBeenCalledWith(window.progressInterval);
        expect(window.currentInstallationId).toBeNull();
        expect(window.loadInstallations).toHaveBeenCalled();
    });

    test('should show alert on cancellation by ID failure', async () => {
        fetch.mockReset();
        fetch.mockResponseOnce(JSON.stringify({ success: false, error: 'Cancel error' }), { status: 500 });

        await window.cancelInstallationById('test-id');

        expect(showAlertSpy).toHaveBeenCalledWith('Failed to cancel installation: Cancel error', 'danger');
    });
});

describe('deleteInstallation', () => {
    let showAlertSpy;

    beforeEach(() => {
        showAlertSpy = jest.spyOn(window, 'showAlert').mockImplementation(() => {});
        jest.spyOn(window, 'loadInstallations').mockImplementation(() => {});
        jest.spyOn(window, 'loadStats').mockImplementation(() => {});
        window.confirm = jest.fn(() => true); // Mock confirm to return true
        fetch.mockResponseOnce(JSON.stringify({ success: true }), { status: 200 });
    });

    test('should delete installation successfully', async () => {
        await window.deleteInstallation('test-id');

        expect(window.confirm).toHaveBeenCalled();
        expect(fetch).toHaveBeenCalledWith(
            '/api/v1/installation/test-id',
            expect.objectContaining({ method: 'DELETE' })
        );
        expect(showAlertSpy).toHaveBeenCalledWith('Installation deleted', 'info');
        expect(window.loadInstallations).toHaveBeenCalled();
        expect(window.loadStats).toHaveBeenCalled();
    });

    test('should show alert on deletion failure', async () => {
        fetch.mockReset();
        fetch.mockResponseOnce(JSON.stringify({ success: false, error: 'Delete error' }), { status: 500 });

        await window.deleteInstallation('test-id');

        expect(showAlertSpy).toHaveBeenCalledWith('Failed to delete installation: Delete error', 'danger');
    });
});

describe('viewInstallationDetails', () => {
    let showAlertSpy;

    beforeEach(() => {
        showAlertSpy = jest.spyOn(window, 'showAlert').mockImplementation(() => {});
        fetch.mockResponseOnce(JSON.stringify({
            installation_id: 'test-id',
            mode: 'all_in_one',
            status: 'success',
            progress_percentage: 100,
            duration: 60,
            error_message: null
        }), { status: 200 });
    });

    test('should display installation details', async () => {
        const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});

        await window.viewInstallationDetails('test-id');

        expect(fetch).toHaveBeenCalledWith('/api/v1/installation/test-id/status');
        expect(alertSpy).toHaveBeenCalledWith(expect.stringContaining('Installation ID: test-id'));
        expect(showAlertSpy).not.toHaveBeenCalled();
    });

    test('should show alert on details fetch failure', async () => {
        fetch.mockReset();
        fetch.mockResponseOnce(JSON.stringify({ success: false, error: 'Details error' }), { status: 500 });

        await window.viewInstallationDetails('test-id');

        expect(showAlertSpy).toHaveBeenCalledWith('Error loading installation details: Details error', 'danger');
    });
});
