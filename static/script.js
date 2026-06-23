document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const imageFolderInput = document.getElementById('image-folder-input');
    const labelFolderInput = document.getElementById('label-folder-input');
    const runBtn = document.getElementById('run-btn');
    const clearConsoleBtn = document.getElementById('clear-console-btn');
    const consoleBox = document.getElementById('console-box');
    const statusMessage = document.getElementById('status-message');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressBar = document.getElementById('progress-bar');
    const systemStatus = document.getElementById('system-status');
    
    // Stats elements
    const statTotal = document.getElementById('stat-total');
    const statProcessed = document.getElementById('stat-processed');
    const statSkipped = document.getElementById('stat-skipped');

    let eventSource = null;
    let totalImages = 0;
    let skippedCount = 0;

    // Helper: Append log line to console
    function appendLog(text, type = 'system') {
        const line = document.createElement('div');
        line.classList.add('console-line', `${type}-line`);
        
        // Add timestamp prefix for premium feel
        const time = new Date().toLocaleTimeString();
        line.innerText = `[${time}] ${text}`;
        
        consoleBox.appendChild(line);
        consoleBox.scrollTop = consoleBox.scrollHeight;
    }

    // Helper: Update System Status Badge
    function updateStatusBadge(status, text) {
        const dot = systemStatus.querySelector('.status-dot');
        const statusText = systemStatus.querySelector('.status-text');
        
        dot.className = 'status-dot';
        if (status === 'idle') {
            dot.classList.add('green');
            statusText.innerText = text || 'System Idle';
        } else if (status === 'running') {
            dot.classList.add('yellow');
            statusText.innerText = text || 'Running...';
        } else if (status === 'error') {
            dot.className = 'status-dot'; // standard red
            dot.style.backgroundColor = '#ef4444';
            dot.style.boxShadow = '0 0 8px #ef4444';
            statusText.innerText = text || 'Pipeline Error';
        } else if (status === 'success') {
            dot.className = 'status-dot';
            dot.style.backgroundColor = '#06b6d4';
            dot.style.boxShadow = '0 0 8px #06b6d4';
            statusText.innerText = text || 'Finished';
        }
    }

    // Reset UI before a run
    function resetPipelineUI() {
        totalImages = 0;
        skippedCount = 0;
        statTotal.innerText = '0';
        statProcessed.innerText = '0';
        statSkipped.innerText = '0';
        progressBar.style.width = '0%';
        progressPercentage.innerText = '0%';
        statusMessage.innerText = 'Initializing...';
        
        // Disable controls
        imageFolderInput.disabled = true;
        labelFolderInput.disabled = true;
        document.querySelectorAll('.browse-btn').forEach(btn => btn.disabled = true);
        runBtn.disabled = true;
        runBtn.querySelector('.btn-text').innerText = 'Annotating...';
        runBtn.querySelector('.btn-icon').className = 'fa-solid fa-spinner fa-spin';
        
        updateStatusBadge('running', 'Processing Dataset');
    }

    // Restore UI after run completes or fails
    function restorePipelineUI(status, statusText) {
        imageFolderInput.disabled = false;
        labelFolderInput.disabled = false;
        document.querySelectorAll('.browse-btn').forEach(btn => btn.disabled = false);
        runBtn.disabled = false;
        runBtn.querySelector('.btn-text').innerText = 'Start Annotation';
        runBtn.querySelector('.btn-icon').className = 'fa-solid fa-play';
        
        updateStatusBadge(status, statusText);
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    }

    // Run Annotation Event Handler
    runBtn.addEventListener('click', () => {
        const imageFolder = imageFolderInput.value.trim();
        const labelFolder = labelFolderInput.value.trim();
        
        if (!imageFolder) {
            alert('Please specify the image directory path.');
            return;
        }

        resetPipelineUI();
        appendLog(`Initiating annotation pipeline for folder: ${imageFolder}`, 'system');

        // Construct SSE stream url
        const params = new URLSearchParams({
            image_folder: imageFolder,
            label_folder: labelFolder
        });
        
        eventSource = new EventSource(`/run?${params.toString()}`);

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.error) {
                appendLog(`[ERROR] ${data.error}`, 'error');
                statusMessage.innerText = 'An error occurred during execution.';
                restorePipelineUI('error', 'Pipeline Error');
                return;
            }

            const message = data.message;
            
            // Parse message outputs to update dashboard counters
            if (message.startsWith('Found')) {
                // E.g., "Found 123 images to process..."
                const match = message.match(/Found (\d+) images/);
                if (match) {
                    totalImages = parseInt(match[1], 10);
                    statTotal.innerText = totalImages;
                    statusMessage.innerText = `Dataset initialized: ${totalImages} files.`;
                }
                appendLog(message, 'system');
            } 
            else if (message.startsWith('Progress:')) {
                // E.g., "Progress: 12/123 | Done: image.jpg"
                const match = message.match(/Progress: (\d+)\/(\d+) \| Done: (.*)/);
                if (match) {
                    const current = parseInt(match[1], 10);
                    const total = parseInt(match[2], 10);
                    const filename = match[3];
                    
                    const pct = Math.round((current / total) * 100);
                    progressBar.style.width = `${pct}%`;
                    progressPercentage.innerText = `${pct}%`;
                    
                    statProcessed.innerText = current;
                    statusMessage.innerText = `Processing: ${filename}`;
                    
                    appendLog(message, 'progress');
                }
            } 
            else if (message.startsWith('Skipped:')) {
                skippedCount++;
                statSkipped.innerText = skippedCount;
                appendLog(message, 'skip');
            } 
            else if (message.startsWith('SUCCESS:')) {
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }
                progressBar.style.width = '100%';
                progressPercentage.innerText = '100%';
                statusMessage.innerText = 'Annotation process complete!';
                appendLog(message, 'success');
                restorePipelineUI('success', 'Pipeline Finished');
            } 
            else if (message.startsWith('Done:')) {
                appendLog(message, 'done');
            }
            else {
                appendLog(message, 'system');
            }
        };

        eventSource.onerror = (err) => {
            console.error('EventSource connection error:', err);
            appendLog('EventSource connection interrupted. Check backend logs.', 'error');
            statusMessage.innerText = 'Connection error.';
            restorePipelineUI('error', 'Connection Error');
        };
    });

    // Clear console action
    clearConsoleBtn.addEventListener('click', () => {
        consoleBox.innerHTML = '<div class="console-line system-line">[SYSTEM] Console log cleared. Ready.</div>';
    });

    // Bind native directory picker events
    const imagePicker = document.getElementById('image-folder-picker');
    const labelPicker = document.getElementById('label-folder-picker');

    function handlePickerChange(picker, targetInput) {
        const files = picker.files;
        if (!files || files.length === 0) return;

        // Extract folder name from the first file's webkitRelativePath
        const firstFile = files[0];
        const relativePath = firstFile.webkitRelativePath;
        const parts = relativePath.split('/');
        const folderName = parts[0]; 
        const fileName = firstFile.name;

        // Set loading message
        targetInput.value = "Resolving host path...";

        // Call resolution endpoint
        const params = new URLSearchParams({
            folder_name: folderName,
            first_file: fileName
        });

        fetch(`/api/resolve_folder?${params.toString()}`)
            .then(res => {
                if (!res.ok) throw new Error('Failed to resolve path');
                return res.json();
            })
            .then(data => {
                if (data.error) {
                    alert(`Could not resolve folder: ${data.error}`);
                    targetInput.value = "";
                    return;
                }
                targetInput.value = data.host_path;
            })
            .catch(err => {
                console.error(err);
                alert("Error resolving folder path. Please type it manually.");
                targetInput.value = "";
            });
    }

    imagePicker.addEventListener('change', () => {
        handlePickerChange(imagePicker, imageFolderInput);
    });

    labelPicker.addEventListener('change', () => {
        handlePickerChange(labelPicker, labelFolderInput);
    });
});
