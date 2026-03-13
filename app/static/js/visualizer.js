// Generic Three.js Animated Background Logic
document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("canvas-container");
    if (!container) return; // Stop if there's no canvas container on the page

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // Create an abstract "knowledge" icosahedron
    const geometry = new THREE.IcosahedronGeometry(3, 1);

    // Wireframe glowing material
    const material = new THREE.MeshPhongMaterial({
        color: 0x6366f1,
        wireframe: true,
        emissive: 0x312e81,
        emissiveIntensity: 0.5,
        transparent: true,
        opacity: 0.8
    });

    // Inner solid core
    const coreMaterial = new THREE.MeshPhongMaterial({
        color: 0x8b5cf6,
        transparent: true,
        opacity: 0.4,
        shininess: 100
    });

    const wireframeMesh = new THREE.Mesh(geometry, material);
    const coreMesh = new THREE.Mesh(new THREE.IcosahedronGeometry(2.8, 2), coreMaterial);

    const group = new THREE.Group();
    group.add(wireframeMesh);
    group.add(coreMesh);
    scene.add(group);

    // Lighting
    const light1 = new THREE.PointLight(0xffffff, 1, 100);
    light1.position.set(10, 10, 10);
    scene.add(light1);

    const light2 = new THREE.PointLight(0x8b5cf6, 2, 50);
    light2.position.set(-10, -10, 5);
    scene.add(light2);

    camera.position.z = 8;

    // Position it depending on the page (center or right)
    if (window.location.pathname === '/' || window.location.pathname === '/auth/login') {
        group.position.set(2, 0, 0);
    } else {
        group.position.set(5, 0, -5); // Move far right on dashboards
    }

    let mouseX = 0;
    let mouseY = 0;
    let targetX = 0;
    let targetY = 0;

    const windowHalfX = window.innerWidth / 2;
    const windowHalfY = window.innerHeight / 2;

    document.addEventListener('mousemove', (event) => {
        mouseX = (event.clientX - windowHalfX) * 0.001;
        mouseY = (event.clientY - windowHalfY) * 0.001;
    });

    // Animation Loop
    function animate() {
        requestAnimationFrame(animate);

        targetX = mouseX * 0.5;
        targetY = mouseY * 0.5;

        // Smooth rotation
        group.rotation.y += 0.003;
        group.rotation.x += 0.002;

        // Mouse interaction
        wireframeMesh.rotation.y += 0.05 * (targetX - wireframeMesh.rotation.y);
        wireframeMesh.rotation.x += 0.05 * (targetY - wireframeMesh.rotation.x);

        renderer.render(scene, camera);
    }

    animate();

    // Resize handler
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
});
